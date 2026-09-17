# Human-readable research timeline

This timeline separates implementation, architecture-enabled possibility, and empirical observation. UNKNOWN means the surviving canonical source did not record the field.

## EXP-4.0 — update4 multi channel v04

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No final report survives; consult preserved structured artifacts.

**WHAT IT MEANS:** No final report survives; consult preserved structured artifacts.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.1 — update41 perceptual cue v041

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No final report survives; consult preserved structured artifacts.

**WHAT IT MEANS:** No final report survives; consult preserved structured artifacts.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.2 — update42 mds v042

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No final report survives; consult preserved structured artifacts.

**WHAT IT MEANS:** No final report survives; consult preserved structured artifacts.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.3 — update43 epistemic lockout v043

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No final report survives; consult preserved structured artifacts.

**WHAT IT MEANS:** No final report survives; consult preserved structured artifacts.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.4 — update44 sensorimotor bootstrap v044

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No final report survives; consult preserved structured artifacts.

**WHAT IT MEANS:** No final report survives; consult preserved structured artifacts.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.5 — update45 prospective valuation v045

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** | Arm | MP candidates | Prospective ≠0 | Selected | |---|---|---|---| | A no-prospective | 21/21 | 0 | 0 | | B/C prospective | 21/21 | 63 | 0 | | D experience ablated | 0 | 0 | 0 | | E prediction ablated | 21/21 | 0 | 0 | Policy still WAIT×60 in phase2 for all bootstrap arms.

**WHAT IT MEANS:** | Arm | MP candidates | Prospective ≠0 | Selected | |---|---|---|---| | A no-prospective | 21/21 | 0 | 0 | | B/C prospective | 21/21 | 63 | 0 | | D experience ablated | 0 | 0 | 0 | | E prediction ablated | 21/21 | 0 | 0 | Policy still WAIT×60 in phase2 for all bootstrap arms.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** MP → retrieval → predicted physical Δ → prospective ordinary value → comparison — **DEMONSTRATED**. MP → selection → execution — **MISSING**.

## EXP-4.6 — update46 object resources v046

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Mixed.** Qty/durability-scaled objects already finite. **Six** replenishing objects (modes 3–4) had no reservoir → infinite identical USE. `quantity` / `durability` via `interaction_state_deltas`. **YES** (initial qty ÷ transfer chunk ± regen). Not a use_count knob. **YES** — full while qty ≥ chunk; last partial; then none. Per-object: {"OBJ-100": {"quantity_changed": true, "effective_uses": 11, "zeroed": true}, "OBJ-103": {"quantity_changed": true, "effective_uses": 8, "zeroed": true}, "OBJ-105": {"quantity_changed": true, "effective_uses": 5, "zeroed": true}, "OBJ-107": {"quantity_changed": true, "effective_uses": 25, "zeroed": false}} **YES** — low_energy 0.0800 vs high_energy -0.0400. **YES** — OBJ-107 regen 0→0.782; effects return. Not newly added; existing autonomous dynamics optional/unchanged. Quantity may be observable; semantic EMPTY/FOOD not exposed. Observer: last USE object + quantity fields. Familiarity does **not** change value (support 1..80 identical). Confidence not used as value. Organism: yes. Depletion→policy: not shown in free run. {'EMIT': 1, 'MOVE': 204, 'USE': 1, 'WAIT': 794}; USE=1 (OBJ-12×1). No depletion cycle, leave, or return. **NO.** Free-policy: USE consequence → learned significance → further USE / leave depleted object. Audit; ecology reservoir gap closed; controlled A/B/knowledge/recovery tests; compact Observer; autonomous artifact. Familia

**WHAT IT MEANS:** **Mixed.** Qty/durability-scaled objects already finite. **Six** replenishing objects (modes 3–4) had no reservoir → infinite identical USE. `quantity` / `durability` via `interaction_state_deltas`. **YES** (initial qty ÷ transfer chunk ± regen). Not a use_count knob. **YES** — full while qty ≥ chunk; last partial; then none. Per-object: {"OBJ-100": {"quantity_changed": true, "effective_uses": 11, "zeroed": true}, "OBJ-103": {"quantity_changed": true, "effective_uses": 8, "zeroed": true}, "OBJ-105": {"quantity_changed": true, "effective_uses": 5, "zeroed": true}, "OBJ-107": {"quantity_changed": true, "effective_uses": 25, "zeroed": false}} **YES** — low_energy 0.0800 vs high_energy -0.0400. 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Free-policy: USE consequence → learned significance → further USE / leave depleted object.

## EXP-4.7 — update47 multi agent v047

**QUESTION:** NOT_RECORDED

**CHANGE:** 1. **Share** geometry, objects, object state, dynamics, fields via one `OrganismWorld` / world dict. 2. **Do not share** memory/experience/retrieval/predictions/body/MPs/decisions — private `mechanisms_by_agent` + per-agent `agent.state` / `bodies`. 3. **Sequential** action apply in `sorted(agent_id)` order; shared dynamics advance once (`advance_dynamics` flag). 4. **No social plumbing** — occupancy blocking + optional anonymous OCCUPANT fragments only. 5. **Observer** — minimal: agent selector + project_tick(agent_id); no large UI rewrite.

**TEST / RESULT:** **Status:** SUCCESS — code + reports synced to lab `<local-lab-tree>` (2026-09-11). Lab smoke: 2-agent Engine step OK. Telemetry `.jsonl` left on box extract only (large); metrics/reports present on lab. 1. **Share** geometry, objects, object state, dynamics, fields via one `OrganismWorld` / world dict. 2. **Do not share** memory/experience/retrieval/predictions/body/MPs/decisions — private `mechanisms_by_agent` + per-agent `agent.state` / `bodies`. 3. **Sequential** action apply in `sorted(agent_id)` order; shared dynamics advance once (`advance_dynamics` flag). 4. **No social plumbing** — occupancy blocking + optional anonymous OCCUPANT fragments only. 5. **Observer** — minimal: agent selector + project_tick(agent_id); no large UI rewrite. | Criterion | Result | |---|---| | Two agents co-exist, separate bodies & psyches | PASS (TWO_NEAR / TWO_FAR) | | MEMORY_ISOLATION | PASS (0 shared fingerprints) | | SHARED_OBJECT_TRACE | PASS (OBJ-12 quantity depleted by A's USE) | | SINGLE still runs | PASS | | Artifacts under `results/update47_multi_agent_v047/` | PASS | | No social reward plumbing | PASS | ```json { "MEMORY_ISOLATION": { "ticks": 40, "action_counts": { "A001": { "WAIT": 32 }, "B001": { "WAIT": 32 } }, "memory_isolation": { "episodes_A": 39, "episodes_B": 39, "pass": true, "shared_episode_fingerprints": 0 }, "memory_episode_counts": { "A001": 39, "B001": 39 }, "final_positi

**WHAT IT MEANS:** **Status:** SUCCESS — code + reports synced to lab `<local-lab-tree>` (2026-09-11). Lab smoke: 2-agent Engine step OK. Telemetry `.jsonl` left on box extract only (large); metrics/reports present on lab. 1. **Share** geometry, objects, object state, dynamics, fields via one `OrganismWorld` / world dict. 2. **Do not share** memory/experience/retrieval/predictions/body/MPs/decisions — private `mechanisms_by_agent` + per-agent `agent.state` / `bodies`. 3. **Sequential** action apply in `sorted(agent_id)` order; shared dynamics advance once (`advance_dynamics` flag). 4. **No social plumbing** — occupancy blocking + optional anonymous OCCUPANT fragments only. 5. **Observer** — minimal: agent selecto

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.7.1 — update471 cross agent trace

**QUESTION:** Physical consequence by one psyche → ordinary experience of another → later decision participation without social semantics? **Experience entry: DEMONSTRATED (under forced observation geometry).** **Later decision participation: NOT DEMONSTRATED.**

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. Yes — persistent quantity change. 2. Yes — B saw quantity 0.72. 3. Agent-available: visible_objects.observable_state.quantity=0.72; no actor provenance. 4. Yes — ordinary spatial/episode experience contained quantity evidence. 5. PARTIAL — evidence remained in memory later; decision-time retrieval not proven. 6. No. 7. No. 8. No. 9. Not asserted. 10. First non-DEMONSTRATED: `{'arrow': 'B_experience→later_retrieval', 'status': 'PARTIAL'}` 11. NO_TRACE: changed=False (True means WAIT did not deplete). 12. TRACE_NOT_OBSERVED: B qty is None=True. 13. EXPERIENCE_ABLATED applied=True. 14. RETRIEVAL_ABLATED prediction_ablated=True. 15. Hidden provenance leaked? False. 16. NEAR_PASSIVE_BODY is a geometry control only; not a social contrast. 17. A persistent quantity change caused by one independent psyche can become physically available to another psyche and enter its ordinary spatial/episode experience without social semantics. Later decision-time retrieval → prediction → prospective valuation → selection is NOT demonstrated. 18. `{'arrow': 'B_experience→later_retrieval', 'status': 'PARTIAL'}`

**WHAT IT MEANS:** 1. Yes — persistent quantity change. 2. Yes — B saw quantity 0.72. 3. Agent-available: visible_objects.observable_state.quantity=0.72; no actor provenance. 4. Yes — ordinary spatial/episode experience contained quantity evidence. 5. PARTIAL — evidence remained in memory later; decision-time retrieval not proven. 6. No. 7. No. 8. No. 9. Not asserted. 10. First non-DEMONSTRATED: `{'arrow': 'B_experience→later_retrieval', 'status': 'PARTIAL'}` 11. NO_TRACE: changed=False (True means WAIT did not deplete). 12. TRACE_NOT_OBSERVED: B qty is None=True. 13. EXPERIENCE_ABLATED applied=True. 14. RETRIEVAL_ABLATED prediction_ablated=True. 15. Hidden provenance leaked? False. 16. NEAR_PASSIVE_BODY is a 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.7.1-POST-CONSEQUENCE-RELAXATION-LATENT-RETURN — update471 post consequence relaxation latent return

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_TEMPORAL_FATE Claims 104 / 104. Canonical: 4.70 G, 4.69 F. Zero new capability. 4.72 not implemented.

**WHAT IT MEANS:** MIXED_TEMPORAL_FATE Claims 104 / 104. Canonical: 4.70 G, 4.69 F. Zero new capability. 4.72 not implemented.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.8 — update48 bounded intake

**QUESTION:** Bounded external→internal transfer with temporal processing **without knowing the object is food**? **YES (physical).** Secondary: existing psyche discovers delayed relation without temporal credit? **NOT DEMONSTRATED.** Elapsed 75.4s

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. USE still immediate full replenish? **No** when intake enabled (intake_mode). 2. Transfer amount: per-interaction cap 0.03 (partial/capacity bounded). 3. Bounded per interaction? **Yes** 4. Bounded by internal capacity? **Yes** (CAPACITY_LIMIT) 5. External qty conserved w.r.t. accepted? **True** 6. Material persists? **Yes** 7. Processing after other actions? **Yes** (ACTION_INDEPENDENCE) 8. Consequence unfolds over ticks: see DELAYED_PROCESSING series 9. Partial transfer: **True** 10. Empty object zero transfer: accepted=0.0 11. Processing ablation isolates consequence: **True** 12. Transfer ablation isolates acquisition: accepted=0.0 13. State-dependent significance: existing valuation retained; physical deltas recorded for low/high energy 14. Material intrinsic +VALUE? **No** 15. FOOD/EAT/HUNGER in cognition? leak PASS=True 16–20. Delayed association / prediction / valuation / selection: **NULL / not demonstrated** 21. First unsupported cognitive arrow: `{'arrow': 'body_consequence→ordinary_experience', 'status': 'PARTIAL'}` 22. Strongest conclusion: Bounded physical intake with delayed internal processing is demonstrated without food semantics; existing psyche does not yet associate delayed consequences with earlier USE. 23. Smallest next experiment: instrument whether ordinary episodes bind USE-time transfer to later processing-time body deltas — still no credit-assignm

**WHAT IT MEANS:** 1. USE still immediate full replenish? **No** when intake enabled (intake_mode). 2. Transfer amount: per-interaction cap 0.03 (partial/capacity bounded). 3. Bounded per interaction? **Yes** 4. Bounded by internal capacity? **Yes** (CAPACITY_LIMIT) 5. External qty conserved w.r.t. accepted? **True** 6. Material persists? **Yes** 7. Processing after other actions? **Yes** (ACTION_INDEPENDENCE) 8. Consequence unfolds over ticks: see DELAYED_PROCESSING series 9. Partial transfer: **True** 10. Empty object zero transfer: accepted=0.0 11. Processing ablation isolates consequence: **True** 12. Transfer ablation isolates acquisition: accepted=0.0 13. State-dependent significance: existing valuation 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.9 — update49 world exchange

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Continuous World–Organism Exchange × Physical Dependency - Maintained `env_material_field` (boundary condition) → per-tick `env_exchange_transfer` - Same `BodyState.internal_materials` and `process_materials` as Update 4.8 - USE discrete transfer still defers processing; continuous env does **not** permanently defer - MOVE affects exchange only via position → local availability - Defaults: `env_exchange_enabled=False` (opt-in) - **ENV_AVAILABLE**: PASS `{'pass_energy_responded': True, 'pass_exchange_nonzero': True, 'pass_internal_rose': True}` - **ENV_DEPRIVED**: PASS `{'pass_exchange_stops': True, 'pass_internal_declines': True}` - **ENV_RESTORED**: PASS `{'pass_exchange_returns': True, 'pass_internal_rises_after': True}` - **EXCHANGE_ABLATED**: PASS `{'pass_internal_flat': True, 'pass_zero_exchange': True}` - **PROCESSING_ABLATED**: PASS `{'pass_exchange_ok': True, 'pass_internal_accumulates': True, 'pass_no_processing_credit': True}` - **SPATIAL_MOVE**: PASS `{'pass_high_gt_low': True, 'pass_moved': True}` - **USE_REGRESSION_4_8**: PASS `{'pass_processing_later': True, 'pass_qty_down': True, 'pass_use_transfer': True}` - **AUTONOMOUS_200**: OK (physics ran; policy null allowed) `{'action_counts': {'WAIT': 200}, 'total_env_exchange': 1.6000000000000012}` - PASS abs_error=0.000e+00 - PASS (0 hits) 1. local availability (maintained field) 2. env_exchange_transfer (bounded per t

**WHAT IT MEANS:** Continuous World–Organism Exchange × Physical Dependency - Maintained `env_material_field` (boundary condition) → per-tick `env_exchange_transfer` - Same `BodyState.internal_materials` and `process_materials` as Update 4.8 - USE discrete transfer still defers processing; continuous env does **not** permanently defer - MOVE affects exchange only via position → local availability - Defaults: `env_exchange_enabled=False` (opt-in) - **ENV_AVAILABLE**: PASS `{'pass_energy_responded': True, 'pass_exchange_nonzero': True, 'pass_internal_rose': True}` - **ENV_DEPRIVED**: PASS `{'pass_exchange_stops': True, 'pass_internal_declines': True}` - **ENV_RESTORED**: PASS `{'pass_exchange_returns': True, 'pa

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** - Not repaired. Physical dependency only; no survival rewards / temporal credit / policy fix.

## EXP-4.9.1 — update491 environmental regulation probe

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Environmental Regulation Probe × Existing Cognition (diagnostic) - IS: trace PHYSICAL → EXPERIENCE → ASSOCIATION → RETRIEVAL → PREDICTION → VALUE → DECISION - IS NOT: homeostasis, seeking, MOVE/exchange rewards, temporal credit assignment, repair - Transitions: **6** A↔B marches (forced = EXPERIMENTER INTERVENTION) - Settle WAIT per arrival: 4 - Seed 17; split field vs uniform 0.5 control { "move_ok": true, "pos_changed": true, "avail_changed": true, "ex_changed": true, "internal_changed": true, "body_changed": true, "avail_range": [ 0.0, 1.0 ], "ex_range": [ 0.0, 0.008 ] } { "first_move": { "move_tick": 2, "\u0394t_move_to_exchange": 7, "\u0394t_move_to_internal": 0, "\u0394t_move_to_body": 0, "\u0394t_move_to_experience": 0, "runtime_order_note": "4.9 env exchange applies each tick; processing same tick unless USE deferred. MOVE\u2192new cell\u2192local avail\u2192exchange can all land on the MOVE tick." }, "first_avail_change": { "move_tick": 9, "\u0394t_move_to_exchange": 0, "\u0394t_move_to_internal": 0, "\u0394t_move_to_body": 0, "\u0394t_move_to_experience": 0, "runtime_order_note": "4.9 env exchange applies each tick; processing same tick unless USE deferred. MOVE\u2192new cell\u2192local avail\u2192exchange can all land on the MOVE tick." } } { "A_action_taken": "YES", "B_pre_action_context": "PARTIAL", "C_post_movement_context": "YES", "D_env_physical_in_perception": 

**WHAT IT MEANS:** Environmental Regulation Probe × Existing Cognition (diagnostic) - IS: trace PHYSICAL → EXPERIENCE → ASSOCIATION → RETRIEVAL → PREDICTION → VALUE → DECISION - IS NOT: homeostasis, seeking, MOVE/exchange rewards, temporal credit assignment, repair - Transitions: **6** A↔B marches (forced = EXPERIMENTER INTERVENTION) - Settle WAIT per arrival: 4 - Seed 17; split field vs uniform 0.5 control { "move_ok": true, "pos_changed": true, "avail_changed": true, "ex_changed": true, "internal_changed": true, "body_changed": true, "avail_range": [ 0.0, 1.0 ], "ex_range": [ 0.0, 0.008 ] } { "first_move": { "move_tick": 2, "\u0394t_move_to_exchange": 7, "\u0394t_move_to_internal": 0, "\u0394t_move_to_body":

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10 — update410 temporal contingency

**QUESTION:** Generic temporal contingency acquisition exists without reward learning (synthetic controls). Ecology pathways use the same mechanism; behavioral self-regulation is **not** claimed. Elapsed: 167.41s

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Temporal Contingency Acquisition × Action–Consequence Binding - Default OFF (`temporal_contingency_enabled=False`) - Lags 0–3; valence-neutral interoceptive deltas; bounded pending/contingencies - `temporal_cue_bucket(visible, percept)` — body_bands omitted - `normalize_action`: `MOVE:x,y` → `MOVE` (else support never accumulates along a path) - Bridge → `prospective_ordinary_value` (same as MP); confidence ≠ value; not RL { "SYNTHETIC_POSITIVE_CONTINGENCY": { "pass_known": true, "pass_positive_delta": true }, "SYNTHETIC_NEGATIVE_CONTINGENCY": { "pass_known": true, "pass_negative_delta": true }, "SYNTHETIC_NULL_CONTINGENCY": { "pass_weak_or_unknown": false }, "TEMPORAL_SHUFFLE": { "pass_shuffle_weaker": true }, "BACKGROUND_CONSEQUENCE": { "pass_not_strong_action_specific": true }, "CONTEXT_DEPENDENT": { "pass_different_signs": true } } - MOVE: n=8 known=0 → **IMPLEMENTED_BUT_UNPROVEN** - USE: n=4 known=0 → **IMPLEMENTED_BUT_UNPROVEN** - OFF: n=0 {'WAIT': 500} wait_only=True known=0 why=7_or_8_prospective_insufficient_vs_motor_cost_or_WAIT_still_wins bounded=True · leakage=PASS - PRE: earlier action/context → later consequence = NULL - POST MOVE: IMPLEMENTED_BUT_UNPROVEN - POST USE: IMPLEMENTED_BUT_UNPROVEN **contingency_update → contingency_stabilization(KNOWN) = PARTIAL** Contingency records form but support/consistency did not reach KNOWN under ecology schedule. Generic tempo

**WHAT IT MEANS:** Temporal Contingency Acquisition × Action–Consequence Binding - Default OFF (`temporal_contingency_enabled=False`) - Lags 0–3; valence-neutral interoceptive deltas; bounded pending/contingencies - `temporal_cue_bucket(visible, percept)` — body_bands omitted - `normalize_action`: `MOVE:x,y` → `MOVE` (else support never accumulates along a path) - Bridge → `prospective_ordinary_value` (same as MP); confidence ≠ value; not RL { "SYNTHETIC_POSITIVE_CONTINGENCY": { "pass_known": true, "pass_positive_delta": true }, "SYNTHETIC_NEGATIVE_CONTINGENCY": { "pass_known": true, "pass_negative_delta": true }, "SYNTHETIC_NULL_CONTINGENCY": { "pass_weak_or_unknown": false }, "TEMPORAL_SHUFFLE": { "pass_shuf

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** - PRE: earlier action/context → later consequence = NULL - POST MOVE: IMPLEMENTED_BUT_UNPROVEN - POST USE: IMPLEMENTED_BUT_UNPROVEN

## EXP-4.10.1 — update4101 ecological stabilization

**QUESTION:** 4.10 can acquire synthetic contingencies when the remembered action is the one being trained. Under forced-action ecology probes, TC correctly binds to selection (WAIT), so USE/MOVE stabilization to KNOWN is **not measured** and remains **NULL** at the override→pending arrow. Free policy stays WAIT-only. Not claimed: environmental understanding, self-maintenance, or that ecology “failed to learn USE” in the organism’s own experience.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Ecological Contingency Stabilization × Background Disambiguation 4.10 params unchanged (`UPDATE4101_FROZEN_PARAMETERS.json`). No new cognition. No threshold lowering, MOVE-cost cut, or policy retune. support ≥ 3.0, contradiction ≤ 0.55, and not background-shared vs WAIT (`action_specific_strength≈0` ⇒ forced UNKNOWN). Forced USE/MOVE curves use `Engine.step({agent: Action(...)})` → `EXTERNAL_OVERRIDE`. TC `open_pending` runs inside selection on the **chosen** action (WAIT), not the **executed** override. Probe after forced USE: contingencies = 4× WAIT L0–L3; USE keys = 0. Observer lag-to-processing (`{'1': 32}`) is physical intake timing, **not** contingency lag_histogram. See `UPDATE4101_PENDING_VS_RECORDS_DIAGNOSIS.md`. - 32/32 valid transfers; became_known=**False**; USE records=**0** - First unsupported: **EXTERNAL_OVERRIDE(executed≠selected) → open_pending(selected) → USE contingency record = NULL** - USE_BACKGROUND_WAIT: WAIT records form (UNKNOWN, strength≈0) under waits - USE_NONTRANSFER: no false global USE records (PASS) - Threshold: `NO_RECORD` (no USE contingency to score) - Matched MOVE/WAIT pairs; MOVE records=**0**; WAIT records form - classification=**INSUFFICIENT_EVIDENCE**; became_known=**False** - First unsupported: **same override→selection binding = NULL** for MOVE records - Noncrossing / lag0 audits written; no action-specific MOVE KNOWN `WAIT:500`, wait_o

**WHAT IT MEANS:** Ecological Contingency Stabilization × Background Disambiguation 4.10 params unchanged (`UPDATE4101_FROZEN_PARAMETERS.json`). No new cognition. No threshold lowering, MOVE-cost cut, or policy retune. support ≥ 3.0, contradiction ≤ 0.55, and not background-shared vs WAIT (`action_specific_strength≈0` ⇒ forced UNKNOWN). Forced USE/MOVE curves use `Engine.step({agent: Action(...)})` → `EXTERNAL_OVERRIDE`. TC `open_pending` runs inside selection on the **chosen** action (WAIT), not the **executed** override. Probe after forced USE: contingencies = 4× WAIT L0–L3; USE keys = 0. Observer lag-to-processing (`{'1': 32}`) is physical intake timing, **not** contingency lag_histogram. See `UPDATE4101_PE

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10.2 — update4102 executed action attribution

**QUESTION:** Executed own-action attribution repaired without privileged override semantics. With frozen 4.10 learner, ecological USE contingencies can reach KNOWN; influence on autonomous selection is limited by the next unsupported arrow above. MOVE attribution works but predictive specificity vs WAIT is not established. Not claimed: agency, food, self-maintenance, intention.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Executed Action Attribution × Temporal Contingency Integrity - `remember_action` stashes decision-time obs + selected; does **not** open TC. - After Engine resolve + integrate, `commit_executed_action(executed)` sets `executed_action` / `last_action`, writes cognition-safe `working.action_execution_evidence={selected_action, executed_action}`, and `open_pending(executed)`. - No intervention-source labels in cognition-facing evidence. - 4.10 temporal params frozen; no value/policy retune. | | selected | executed | temporal key | records | |--|----------|----------|--------------|---------| | PRE USE | WAIT | USE | WAIT | USE=0 | | POST USE | WAIT | USE:OBJ-100 | USE:OBJ-100 | USE=4 (curve→KNOWN at n≥4) | | PRE MOVE | WAIT | MOVE | WAIT | MOVE=0 | | POST MOVE | WAIT | MOVE:… | MOVE | MOVE=4..8; **BACKGROUND_SHARED** | All primary controls PASS (see ACTION_ATTRIBUTION_TABLE.md). TC_OFF→0 records. USE_NO_TRANSFER still keys USE. MOVE_NO_DISPLACEMENT keys MOVE with disp=0. Leakage PASS (docstring false positives cleared). - **USE**: became_known=**True** (known≥3 from n=4 onward; support tracks n). Lag-to-proc observer mostly lag1; TC strongest often L2. - **MOVE**: records form; classification=**BACKGROUND_SHARED** (strength≈0 vs WAIT exchange). Valid ecological null — not fixed. - Free500: WAIT-only. - retrieval_eligible=True - retrieved_at_decision=True - prediction_affected=Fals

**WHAT IT MEANS:** Executed Action Attribution × Temporal Contingency Integrity - `remember_action` stashes decision-time obs + selected; does **not** open TC. - After Engine resolve + integrate, `commit_executed_action(executed)` sets `executed_action` / `last_action`, writes cognition-safe `working.action_execution_evidence={selected_action, executed_action}`, and `open_pending(executed)`. - No intervention-source labels in cognition-facing evidence. - 4.10 temporal params frozen; no value/policy retune. | | selected | executed | temporal key | records | |--|----------|----------|--------------|---------| | PRE USE | WAIT | USE | WAIT | USE=0 | | POST USE | WAIT | USE:OBJ-100 | USE:OBJ-100 | USE=4 (curve→KNO

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Probe why KNOWN USE fails to change selection (retrieval miss vs valuation/MOVE-cost/WAIT dominance) — diagnostic only, no retune.

## EXP-4.10.3 — update4103 predictive utilization

**QUESTION:** KNOWN USE is retrieved with intact physical mean_body_delta, but existing prospective mapping drops *_signal keys, so ordinary_value stays 0. Not repaired.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** KNOWN Temporal Evidence x Predictive Utilization (DIAGNOSTIC ONLY) No learner/value/policy/threshold changes. Real ecological USE x 16; KNOWN at n=3. Key: `TC||(('CUE-02-15', 'CUE-08-00', 'CUE-08-17'), ())||USE:OBJ-100||L2` - stored mean_body_delta nonzero: YES (energy_signal=0.00972881170384083) - retrieved preserves delta: YES - prediction accepts USE hit: YES - mapped predicted_signal_deltas nonzero: NO ({}) - ordinary_value: 0.0 - selected: WAIT `accepted temporal mean_body_delta (*_signal) -> map_reserve_deltas_to_signal_deltas -> usable predicted_signal_deltas` = **NULL** temporal mean_body_delta uses *_signal keys; map_reserve_deltas_to_signal_deltas expects energy_delta/hydration_delta or *_signal_delta — result empty 4.10.2 claimed retrieval -> prediction = NULL. Incorrect. Corrected: predicted body delta -> prospective valuation mapping. KNOWN USE is retrieved with intact physical mean_body_delta, but existing prospective mapping drops *_signal keys, so ordinary_value stays 0. Not repaired. Own update: schema alignment of temporal *_signal deltas to valuation keys (diagnostic/repair), without threshold or policy retune. Elapsed: 41.19s

**WHAT IT MEANS:** KNOWN Temporal Evidence x Predictive Utilization (DIAGNOSTIC ONLY) No learner/value/policy/threshold changes. Real ecological USE x 16; KNOWN at n=3. Key: `TC||(('CUE-02-15', 'CUE-08-00', 'CUE-08-17'), ())||USE:OBJ-100||L2` - stored mean_body_delta nonzero: YES (energy_signal=0.00972881170384083) - retrieved preserves delta: YES - prediction accepts USE hit: YES - mapped predicted_signal_deltas nonzero: NO ({}) - ordinary_value: 0.0 - selected: WAIT `accepted temporal mean_body_delta (*_signal) -> map_reserve_deltas_to_signal_deltas -> usable predicted_signal_deltas` = **NULL** temporal mean_body_delta uses *_signal keys; map_reserve_deltas_to_signal_deltas expects energy_delta/hydration_del

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Own update: schema alignment of temporal *_signal deltas to valuation keys (diagnostic/repair), without threshold or policy retune. Elapsed: 41.19s

## EXP-4.10.4 — update4104 schema alignment

**QUESTION:** Acquired temporal physical prediction now reaches existing prospective valuation via schema alignment. WAIT still wins numerically (cost). Not claimed: food, self-maintenance, intention.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Temporal Consequence Schema Alignment x Prospective Valuation Integrity `canonicalize_predicted_body_delta`: temporal `*_signal` (already deltas) -> canonical `*_signal_delta`. Single boundary in prospective_valuation. TC storage / retrieval / thresholds / costs / policy unchanged. stored/retrieved energy_signal unchanged (~0.00972881170384083) PRE map usable: {} -> ordinary_value=0 POST map: {"discomfort_signal_delta": 0.00030000000000000014, "activity_capacity_signal_delta": 0.0, "activity_load_signal_delta": 0.0, "hydration_signal_delta": -0.002999999999999999, "effort_signal_delta": 0.0, "energy_signal_delta": 0.00972881170384083, "fatigue_signal_delta": 0.00360000000000002} ordinary_value=0.014153896132880353 epistemic=POSITIVE USE temporal score=-0.3759482532825476 WAIT endogenous score=0.03618038949052062 selected=WAIT same delta value_low=0.012075621194112372 value_high=-0.003885051576642101 {'WAIT': 500} {"arrow": "candidate comparison -> selection (WAIT still wins)", "status": "PARTIAL", "note": "predictive utilization through valuation DEMONSTRATED; behavioral change NULL"} Acquired temporal physical prediction now reaches existing prospective valuation via schema alignment. WAIT still wins numerically (cost). Not claimed: food, self-maintenance, intention. Why USE score remains below WAIT given nonzero prospective value (cost vs benefit diagnostic only; no retune). 

**WHAT IT MEANS:** Temporal Consequence Schema Alignment x Prospective Valuation Integrity `canonicalize_predicted_body_delta`: temporal `*_signal` (already deltas) -> canonical `*_signal_delta`. Single boundary in prospective_valuation. TC storage / retrieval / thresholds / costs / policy unchanged. stored/retrieved energy_signal unchanged (~0.00972881170384083) PRE map usable: {} -> ordinary_value=0 POST map: {"discomfort_signal_delta": 0.00030000000000000014, "activity_capacity_signal_delta": 0.0, "activity_load_signal_delta": 0.0, "hydration_signal_delta": -0.002999999999999999, "effort_signal_delta": 0.0, "energy_signal_delta": 0.00972881170384083, "fatigue_signal_delta": 0.00360000000000002} ordinary_val

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Why USE score remains below WAIT given nonzero prospective value (cost vs benefit diagnostic only; no retune). Elapsed: 161.77s

## EXP-4.10.5 — update4105 action economics

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Action Economics Diagnostic × WAIT Attractor Decomposition No retune. No cost/value/policy/ecology changes. `mechanistic_mind/psyche/sensorimotor.py` `select_proposal.score`: - `score = ordinary_action_value` - if action is USE/MOVE/PUSH/TAKE **and** severe: `score -= 0.35 + 0.04` - WAIT: no penalty severe := energy_signal < 0.18 OR hydration_signal < 0.18 OR fatigue_signal > 0.82 - body hydration_signal=0.0 → severe=True (triggered by hydration) - USE temporal ordinary≈0.014052 - USE penalty=0.39 → USE score≈-0.375948 - WAIT endogenous ordinary/score≈0.036180 - selected=WAIT - all reconstruct errors ~0 **Physiology suppression** in selection (0.35+0.04), NOT Dynamic Activity Capacity motor cost in this path. activity_capacity=1.0 load=0.0 do not enter this score(). Positive endogenous ordinary from OrganismValuation `values.by_action['WAIT']`; exempt from severe penalty. Δordinary from TC≈0.009231; still far below clearing 0.39 penalty. Need ordinary_USE ≈ 0.4262 at fixed penalty; current ≈ 0.0141; ratio≈0.0330 {'WAIT': 500} — WAIT-only; severe_frac high in timeline. STABLE SCORE-DOMINANT WAIT ATTRACTOR / COST-DOMINATED ACTIVE-ACTION SUPPRESSION Selection is consistent with the physical economy encoded in score(): acquired USE benefit is real (~+0.014) but hydration-gated severe penalty (−0.39) dominates; WAIT keeps small positive ordinary. Cognition is using acquired experien

**WHAT IT MEANS:** Action Economics Diagnostic × WAIT Attractor Decomposition No retune. No cost/value/policy/ecology changes. `mechanistic_mind/psyche/sensorimotor.py` `select_proposal.score`: - `score = ordinary_action_value` - if action is USE/MOVE/PUSH/TAKE **and** severe: `score -= 0.35 + 0.04` - WAIT: no penalty severe := energy_signal < 0.18 OR hydration_signal < 0.18 OR fatigue_signal > 0.82 - body hydration_signal=0.0 → severe=True (triggered by hydration) - USE temporal ordinary≈0.014052 - USE penalty=0.39 → USE score≈-0.375948 - WAIT endogenous ordinary/score≈0.036180 - selected=WAIT - all reconstruct errors ~0 **Physiology suppression** in selection (0.35+0.04), NOT Dynamic Activity Capacity motor 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Diagnostic/experimental: under what **naturally occurring** hydration/energy trajectories does severe clear so USE score can compete — without retuning 0.35/0.04 (ecology/physiology trajectory study).

## EXP-4.10.6 — update4106 natural physiological window

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **E — STARTS SEVERE / NO NATURAL PRE-SEVERE WINDOW FROM CANONICAL START** Knowledge timing class: **E** — Canonical run begins severe (and/or Phase B release already severe). USE-below-WAIT class: **MIXED** (BENEFIT_TOO_SMALL, SEVERE_GATE_ACTIVATES_BEFORE_COMPETITION, NO_RELEVANT_NATURAL_WINDOW, WAIT_POSITIVE_VALUE)

**WHAT IT MEANS:** **E — STARTS SEVERE / NO NATURAL PRE-SEVERE WINDOW FROM CANONICAL START** Knowledge timing class: **E** — Canonical run begins severe (and/or Phase B release already severe). USE-below-WAIT class: **MIXED** (BENEFIT_TOO_SMALL, SEVERE_GATE_ACTIVATES_BEFORE_COMPETITION, NO_RELEVANT_NATURAL_WINDOW, WAIT_POSITIVE_VALUE)

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10.7 — update4107 developmental initialization

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **E_plus_active**

**WHAT IT MEANS:** **E_plus_active**

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10.8 — update4108 ordinary action economy

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **B + C — INTERNAL ECONOMY PREFERS WAIT; REALIZED ORDINARY FAVORS USE AT H≥3** Matched CF (S0–S3): predicted_diff USE−WAIT ≈ −0.019…−0.028 (WAIT ahead), but realized_ordinary_diff > 0 from H3 onward (USE ahead), H1 tie (~0). Habit (0.03) dominates WAIT score; env exchange not involved.

**WHAT IT MEANS:** **B + C — INTERNAL ECONOMY PREFERS WAIT; REALIZED ORDINARY FAVORS USE AT H≥3** Matched CF (S0–S3): predicted_diff USE−WAIT ≈ −0.019…−0.028 (WAIT ahead), but realized_ordinary_diff > 0 from H3 onward (USE ahead), H1 tie (~0). Habit (0.03) dominates WAIT score; env exchange not involved.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10.9 — update4109 temporal habit alignment

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** WAIT non-severe dominance is mostly repetition-habit (+0.03) added into ordinary-value space without consequence grounding; KNOWN USE predicts a single lag (L2) body delta, while matched physics favors USE from H>=3. Multi-lag records exist but selection collapses to one lag — first missing arrow is joint bounded trajectory at decision time.

**WHAT IT MEANS:** WAIT non-severe dominance is mostly repetition-habit (+0.03) added into ordinary-value space without consequence grounding; KNOWN USE predicts a single lag (L2) body delta, while matched physics favors USE from H>=3. Multi-lag records exist but selection collapses to one lag — first missing arrow is joint bounded trajectory at decision time.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.10.10 — update41010 bounded prospective trajectory

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Lag records are cumulative T0→TL; summing double-counts; bounded horizon-specific shadow improves structure over single-lag collapse; direct repetition→+ordinary value is ungrounded physically while epistemic support from experience remains legitimate; canonical WAIT>USE in non-severe is largely habit prior + short horizon

**WHAT IT MEANS:** Lag records are cumulative T0→TL; summing double-counts; bounded horizon-specific shadow improves structure over single-lag collapse; direct repetition→+ordinary value is ungrounded physically while epistemic support from experience remains legitimate; canonical WAIT>USE in non-severe is largely habit prior + short horizon

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Smallest next: optional shadow-only policy readout that keeps predictive ordinary and policy prior SEPARATE (no retune), OR extend DEFAULT_LAGS diagnostically if physical delay requires H10 — still no habit_weight/gate retune Elapsed_s: 285.8 first_severe: 139

## EXP-4.10.11 — update41011 trajectory calibration

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** H3≈+0.013 is an unconditioned EMA mean of absolute USE cumulative deltas; physics is deterministic so snapshot mismatch is bias from history/state aggregation + absolute vs action-specific representation, not stochastic noise. Multi-lag structure≠calibration. Temporal valuation of H1/H2/H3 remains MISSING.

**WHAT IT MEANS:** H3≈+0.013 is an unconditioned EMA mean of absolute USE cumulative deltas; physics is deterministic so snapshot mismatch is bias from history/state aggregation + absolute vs action-specific representation, not stochastic noise. Multi-lag structure≠calibration. Temporal valuation of H1/H2/H3 remains MISSING.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Smallest next: shadow-only action-specific (USE−WAIT) consequence estimate and/or state-conditioned TC keys using existing nonsemantic body features — still no habit_weight/gate retune, no policy integration, no gamma Elapsed_s: 298.5 first_severe: 139

## EXP-4.11 — update411 prospective self state

**QUESTION:** NOT_RECORDED

**CHANGE:** - Coarse cognition-visible state key: energy/hydration/fatigue L/M/H (`coarse_body_state_key`) - TC records keyed with state; retrieval prefers EXACT state, falls back to LEGACY/OTHER - `predicted_state(A,L) = current + cumulative_delta(A,L)` - WAIT acquired/predicted as real no-intervention trajectory - `A−WAIT` diagnostic from independently predicted states only (not value) - Per-horizon ordinary valuation for Observer; **no** H1+H2+H3 aggregation - Prospective path does **not** add habit×0.03

**TEST / RESULT:** Prospective Self-State × Counterfactual Physical Futures - Coarse cognition-visible state key: energy/hydration/fatigue L/M/H (`coarse_body_state_key`) - TC records keyed with state; retrieval prefers EXACT state, falls back to LEGACY/OTHER - `predicted_state(A,L) = current + cumulative_delta(A,L)` - WAIT acquired/predicted as real no-intervention trajectory - `A−WAIT` diagnostic from independently predicted states only (not value) - Per-horizon ordinary valuation for Observer; **no** H1+H2+H3 aggregation - Prospective path does **not** add habit×0.03 Action counts: {'WAIT': 200} State keys seen: ['S:eLhLfL', 'S:eLhLfM', 'S:eMhMfL'] 1. Future organism state under **current** coarse body state (state-conditioned retrieval) 2. Explicit **WAIT** evolving trajectory (not identity) 3. Multi-horizon **predicted states** H1/H2/H3 kept separate 4. Intervention difference USE−WAIT when both known 5. Per-horizon ordinary valuations without combining them Free-policy change is **not** required for PASS. Counts: {'WAIT': 200} If state-conditioned predicted-later-organism-state under own candidates is present, researchers may cautiously call this a **primitive prospective self-model**. Not self-awareness. Elapsed_s: 190.6

**WHAT IT MEANS:** Prospective Self-State × Counterfactual Physical Futures - Coarse cognition-visible state key: energy/hydration/fatigue L/M/H (`coarse_body_state_key`) - TC records keyed with state; retrieval prefers EXACT state, falls back to LEGACY/OTHER - `predicted_state(A,L) = current + cumulative_delta(A,L)` - WAIT acquired/predicted as real no-intervention trajectory - `A−WAIT` diagnostic from independently predicted states only (not value) - Per-horizon ordinary valuation for Observer; **no** H1+H2+H3 aggregation - Prospective path does **not** add habit×0.03 Action counts: {'WAIT': 200} State keys seen: ['S:eLhLfL', 'S:eLhLfM', 'S:eMhMfL'] 1. Future organism state under **current** coarse body stat

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.12 — update412 transition composition

**QUESTION:** Allowed if OK: acquired transition composition; composed prospective trajectory. Not claimed: planning, imagination, foresight, self-awareness. Elapsed_s: 49.5

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. PARTIAL/UNKNOWN 2. {'energy_err_s1': 0.006199999999999983, 'energy_err_s2': None, 'note': 'support judged by error magnitude, not exact equality'} 3. COMPOSITION_UNKNOWN_BEFORE_PHYSICS 4. {'DIRECT': 2, 'COMPOSABLE': 4, 'UNKNOWN': 3} 5. NOT TESTED

**WHAT IT MEANS:** 1. PARTIAL/UNKNOWN 2. {'energy_err_s1': 0.006199999999999983, 'energy_err_s2': None, 'note': 'support judged by error magnitude, not exact equality'} 3. COMPOSITION_UNKNOWN_BEFORE_PHYSICS 4. {'DIRECT': 2, 'COMPOSABLE': 4, 'UNKNOWN': 3} 5. NOT TESTED

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.12.2 — update4122 history dependent prospective space

**QUESTION:** If acceptance holds: different acquired histories produce different representable prospective spaces from a matched cognition-visible present. Not claimed: imagination, planning, personality. Elapsed_s: 279.6

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** History-Dependent Prospective Space × Prospective Psychology Observer PASS — fields: ['state_key', 'energy_signal', 'hydration_signal', 'fatigue_signal'] Physical availability matched: PASS A: USE + MOVE@S:eMhMfL (n_move=12); target sequence seen=NO B: USE only; target sequence seen=NO A USE→MOVE: **OK** B USE→MOVE: **UNKNOWN** A-only composed: ['MOVE:1,0→MOVE:1,0', 'MOVE:1,0→USE:OBJ-100', 'MOVE:1,0→WAIT', 'USE:OBJ-100→MOVE:1,0', 'WAIT→MOVE:1,0'] B-only composed: [] Shared composed: ['USE:OBJ-100→USE:OBJ-100', 'USE:OBJ-100→WAIT', 'WAIT→USE:OBJ-100', 'WAIT→WAIT'] Missing-link ablation on A → UNKNOWN Same-history instances USE→MOVE: OK vs OK After B acquires MOVE@S:eMhMfL only: B USE→MOVE → OK (novelty=NO) If acceptance holds: different acquired histories produce different representable prospective spaces from a matched cognition-visible present. Not claimed: imagination, planning, personality. Elapsed_s: 279.6

**WHAT IT MEANS:** History-Dependent Prospective Space × Prospective Psychology Observer PASS — fields: ['state_key', 'energy_signal', 'hydration_signal', 'fatigue_signal'] Physical availability matched: PASS A: USE + MOVE@S:eMhMfL (n_move=12); target sequence seen=NO B: USE only; target sequence seen=NO A USE→MOVE: **OK** B USE→MOVE: **UNKNOWN** A-only composed: ['MOVE:1,0→MOVE:1,0', 'MOVE:1,0→USE:OBJ-100', 'MOVE:1,0→WAIT', 'USE:OBJ-100→MOVE:1,0', 'WAIT→MOVE:1,0'] B-only composed: [] Shared composed: ['USE:OBJ-100→USE:OBJ-100', 'USE:OBJ-100→WAIT', 'WAIT→USE:OBJ-100', 'WAIT→WAIT'] Missing-link ablation on A → UNKNOWN Same-history instances USE→MOVE: OK vs OK After B acquires MOVE@S:eMhMfL only: B USE→MOVE → OK

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.13 — Acquired Expectation × Prediction Violation

**QUESTION:** Allowed: acquired expectation, prediction confirmation/mismatch/violation, history-dependent prediction violation, expectation-relative error, transition-localized prediction error. Not claimed: emotion, subjective surprise, consciousness. Cautious researcher note: STRONG+KNOWN prediction can be quantitatively mismatched while WEAK/UNKNOWN with the same physical event are not classified as violated expectation — a functional precursor to surprise only at the measurement layer, not an emotion.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. YES — UNKNOWN_SAME_EVENT status=NO_PREDICTIVE_BASELINE while STRONG_EXPECTATION_VIOLATION status=PREDICTION_MISMATCH. UNKNOWN is NO_PREDICTIVE_BASELINE, not maximal violation. 2. Primary H3: STRONG abs_L1=0.015075000000000033 support=12.0 contrad=0.3281380950315635 status=PREDICTION_MISMATCH; WEAK abs_L1=0.015075000000000033 support=2.0 status=NO_PREDICTIVE_BASELINE; BROAD contrad=0.3450889413185585 status=PREDICTION_CONFIRMED. Identical abs_L1 for STRONG and WEAK (0.015075000000000033); epistemic significance differs (KNOWN+MISMATCH vs NO_PREDICTIVE_BASELINE). No σ-standardized score. 3. YES: SAME_PRESENT=PASS SAME_ACTION=PASS SAME_REALIZED=PASS. Profiles STRONG=PREDICTION_MISMATCH, WEAK=NO_PREDICTIVE_BASELINE, UNKNOWN=NO_PREDICTIVE_BASELINE, BROAD=PREDICTION_CONFIRMED. 4. Composed attribution=BOTH_EDGES_CONFIRMED; edge1=PREDICTION_CONFIRMED edge2=PREDICTION_CONFIRMED. Per-transition errors only. 5. Ordinary EMA updates both cases (support_delta match=1.0 violation=1.0; mean_energy_shift match=0.0 violation=-0.0010673076923076947). No violation-gated learning rule. 6. Prospective probes recorded before/after; STRONG use_L before={'composed_USE_MOVE': {'composition': 'UNKNOWN', 'edge_a': {'status': 'OK', 'support': 12.0}, 'edge_b': {'status': 'UNKNOWN', 'support': 0.0}, 'status': 'UNKNOWN'}, 'record_USE_L': {'confidence': 0.5616301621581267, 'contradiction': 0.32813809503156

**WHAT IT MEANS:** 1. YES — UNKNOWN_SAME_EVENT status=NO_PREDICTIVE_BASELINE while STRONG_EXPECTATION_VIOLATION status=PREDICTION_MISMATCH. UNKNOWN is NO_PREDICTIVE_BASELINE, not maximal violation. 2. Primary H3: STRONG abs_L1=0.015075000000000033 support=12.0 contrad=0.3281380950315635 status=PREDICTION_MISMATCH; WEAK abs_L1=0.015075000000000033 support=2.0 status=NO_PREDICTIVE_BASELINE; BROAD contrad=0.3450889413185585 status=PREDICTION_CONFIRMED. Identical abs_L1 for STRONG and WEAK (0.015075000000000033); epistemic significance differs (KNOWN+MISMATCH vs NO_PREDICTIVE_BASELINE). No σ-standardized score. 3. YES: SAME_PRESENT=PASS SAME_ACTION=PASS SAME_REALIZED=PASS. Profiles STRONG=PREDICTION_MISMATCH, WEAK

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.13.1 — Expectation Adaptation × Alternating Consequences

**QUESTION:** Allowed: expectation adaptation, regime-change mismatch, alternating history, central-estimate collapse, unobserved mean prediction, retained contradiction evidence. Not claimed: doubt, confusion, surprise adaptation, belief revision, emotion.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** [ "A_ADAPTIVE_SINGLE_EXPECTATION", "C_UNOBSERVED_MEAN_COLLAPSE", "E_CONTRADICTION_PRESERVES_STRUCTURE" ] A: single central expectation adapts X→Y under ordinary EMA. C: alternating X/Y collapses toward unobserved intermediate Z. E: contradiction rises with incompatible outcomes but does not restore modes.

**WHAT IT MEANS:** [ "A_ADAPTIVE_SINGLE_EXPECTATION", "C_UNOBSERVED_MEAN_COLLAPSE", "E_CONTRADICTION_PRESERVES_STRUCTURE" ] A: single central expectation adapts X→Y under ordinary EMA. C: alternating X/Y collapses toward unobserved intermediate Z. E: contradiction rises with incompatible outcomes but does not restore modes.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Do NOT auto-implement 4.14. Given C+E: next justified question is whether the psyche can retain multiple independently acquired prospective consequences for the same state/action without averaging them into a never-experienced Z (possibly leveraging contradiction evidence).

## EXP-4.14 — Multiple Acquired Consequences

**QUESTION:** Allowed: multiple acquired consequences, multimodal consequence representation, experience-grounded prospective branching, consequence-conditioned composition. Not claimed: doubt, imagination, planning, calibrated probability, consciousness.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. YES — multi supported modes=2; recovers_XY=True; legacy_collapse_Z=True. 2. Unimodal supported modes=1; FALSE_BRANCHING narrow=NO. 3. Rare Y after 10 X: raw_modes=2, supported=1 (support gate MIN=3.0). 4. Regime shift final supported modes=2; raw=2. See CONDITION_MULTI_REGIME_SHIFT.json. 5. YES — multi distinguishes alternating history via separate modes; legacy does not. 6. YES as data — prospective_consequences returns 2 supported predicted states (not collapsed before prospective layer). 7. Branched composition n_branches=2; COMPOSITION_FROM_UNOBSERVED_MEAN=NO. 8. Realize Y vs multi → MATCHES_SUPPORTED_CONSEQUENCE; realize X → MATCHES_SUPPORTED_CONSEQUENCE. Frequency is not used as certainty. 9. Legacy contradiction remains directional inconsistency vs single EMA mean; multi-modes do not redefine it. May stay elevated on legacy Z even when modes separate. 10. {"n_keys": 8, "n_modes_total": 23, "max_modes_per_key": 4, "updates": 382, "approx_bytes_hint": 5112} 11. First unsupported causal arrow: from experience-grounded multiple prospective consequences to any justified selection/attention/commitment among them without smuggling value, calibrated probability, or planning — i.e. whether/how the psyche should act when more than one acquired consequence is representable.

**WHAT IT MEANS:** 1. YES — multi supported modes=2; recovers_XY=True; legacy_collapse_Z=True. 2. Unimodal supported modes=1; FALSE_BRANCHING narrow=NO. 3. Rare Y after 10 X: raw_modes=2, supported=1 (support gate MIN=3.0). 4. Regime shift final supported modes=2; raw=2. See CONDITION_MULTI_REGIME_SHIFT.json. 5. YES — multi distinguishes alternating history via separate modes; legacy does not. 6. YES as data — prospective_consequences returns 2 supported predicted states (not collapsed before prospective layer). 7. Branched composition n_branches=2; COMPOSITION_FROM_UNOBSERVED_MEAN=NO. 8. Realize Y vs multi → MATCHES_SUPPORTED_CONSEQUENCE; realize X → MATCHES_SUPPORTED_CONSEQUENCE. Frequency is not used as cer

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.15 — Prospective Continuity × Branch Resolution

**QUESTION:** Allowed: prospective reconstruction; measured absence of continuity; episode vs acquired-memory distinction. Not claimed: anticipation, imagination, intention, commitment, planning, belief, doubt.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** [ "A_RECONSTRUCTION_ONLY" ]

**WHAT IT MEANS:** [ "A_RECONSTRUCTION_ONLY" ]

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.16 — Persistent Prospective Trace × Partial Realization

**QUESTION:** 1. YES — the t0 trajectory remains in working mechanism state after its first physical match. 2. YES — trace ID, created_tick, predicted vectors, parent links, and DIRECT/COMPOSED provenance remain original. 3. YES — hard reconstruction ablation leaves the old two-node tail available. 4. YES — deleting the episode trace leaves acquired evidence able to create a new trace at t1. 5. YES — the two reciprocal ablations demonstrate continuity and reconstruction independently. 6. YES — one trace survives two successive partial realizations and retains its final t0 node. 7. The affected branches become REALIZED_INCOMPATIBLE; with no compatible branch the trace becomes TRACE_DIVERGED. 8. The branch becomes action-incompatible and the trace ACTION_DIVERGED; policy is not forced to follow it. 9. YES — X/Y episode compatibility changes only trace branches; acquired C1/C2 evidence is unchanged. 10. YES — a later S0 episode creates both X/Y branches again. 11. They coexist with distinct IDs/ticks and may disagree component-wise; neither is ranked. 12. One active trace, <=4 branches, <=3 edges each; O(branches) checks/update and bounded serialized storage. 13. YES, cautiously: the mechanism supports the term persistent prospective expectation. 14. YES, cautiously: reciprocal ablations support functional precursor to anticipation, not anticipation as a human faculty. 15. First unsupported arrow: persistent prospective expectation -> any policy/action-selection consequence.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** PROSPECTIVE_CONTINUITY = PRESENT PROSPECTIVE_RECONSTRUCTION = PRESENT The reciprocal ablations establish that retained t0 state is neither a researcher log nor a numerically identical t1 reconstruction.

**WHAT IT MEANS:** PROSPECTIVE_CONTINUITY = PRESENT PROSPECTIVE_RECONSTRUCTION = PRESENT The reciprocal ablations establish that retained t0 state is neither a researcher log nor a numerically identical t1 reconstruction.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.17 — Persistent Expectation × Fresh Prediction Conflict

**QUESTION:** 1. YES — both are simultaneously present as mechanism-state traces at t1. 2. YES — ordinary acquired histories yield comparable P vs Q with relation INCOMPATIBLE. 3. YES — old created_tick=100, prefix physical realization and fresh reconstruction occur at t1=101. 4. YES — fresh has a new ID/tick and is reconstructed from a separate acquired-evidence key. 5. Only consequence incompatibility produces conflict; distinct provenance with identical P is AGREEMENT. 6. YES — OLD_ONLY/FRESH_ONLY are OLD_UNKNOWN/FRESH_UNKNOWN and never conflict. 7. YES — P and Q remain separate; averaged_prediction is null. 8. P-like reality confirms old and violates fresh. 9. Q-like reality violates old and confirms fresh. 10. YES — ordinarily acquired R-like reality violates both. 11. Any compatible old/fresh branch pair yields OVERLAP; no pair yields INCOMPATIBLE. 12. YES — old P versus fresh {P,Q} is OVERLAP, not conflict. 13. YES — matched S1/Q event gives conflict for history A and agreement for history B. 14. Existing policy selects MOVE:1,0 for its ordinary pre-existing selection reason. 15. NO — the comparison record is not supplied to action selection. 16. NO — Update 4.17 adds researcher measurement only. 17. YES — baseline and post-update sets contain the identical 15 failures; no new regression was introduced. 18. YES — comparable concurrent P/Q incompatibility satisfies the conservative definition. 19. YES, cautiously — as a functional precursor to mechanistic doubt, not doubt. 20. First unsupported arrow: unresolved prospective conflict -> policy/action selection.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** OLD/FRESH_COEXISTENCE = PRESENT PROSPECTIVE_CONFLICT = PRESENT P and Q are concurrent, comparable, ordinarily acquired predictions with temporally distinct provenance. The comparison is researcher-only, preserves both representations, performs no averaging or resolution, and has no policy/value coupling.

**WHAT IT MEANS:** OLD/FRESH_COEXISTENCE = PRESENT PROSPECTIVE_CONFLICT = PRESENT P and Q are concurrent, comparable, ordinarily acquired predictions with temporally distinct provenance. The comparison is researcher-only, preserves both representations, performs no averaging or resolution, and has no policy/value coupling.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.18 — Composed Future Value

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** The strongest condition passed. Independently acquired physical links composed the previously unseen complete sequence `MOVE:EAST → OPEN:GATE → USE:RESOURCE`. Ordinary values by depth were `[-0.04353750000000004, -0.08114999999999999, 0.11984999999999996]`; the shallowest positive value horizon was **3**. The matched evolving WAIT values were `[-0.010237500000000014, -0.020950000000000014, -0.03213750000000002]`. The valuation components are the existing energy, hydration, fatigue and discomfort target-error reductions with weights from `PsycheState.initial_organism_v03`; no new reward exists. Each terminal state is evaluated once from its physical start-to-terminal delta. Supports remain epistemic metadata. First execution component L1 errors were `[0.0, 0.0, 0.0]` and the positive terminal sign was confirmed. Multi-consequence terminal branches remained separate and included both positive and non-positive ordinary valuations. UNKNOWN links stayed UNKNOWN. State, history, and order controls behaved as expected. Policy coupling, backward value propagation, sequence reward, planning, and branch selection are all absent. Existing policy observation selected WAIT while the distant positive composed future was available only to the researcher measurement.

**WHAT IT MEANS:** The strongest condition passed. Independently acquired physical links composed the previously unseen complete sequence `MOVE:EAST → OPEN:GATE → USE:RESOURCE`. Ordinary values by depth were `[-0.04353750000000004, -0.08114999999999999, 0.11984999999999996]`; the shallowest positive value horizon was **3**. The matched evolving WAIT values were `[-0.010237500000000014, -0.020950000000000014, -0.03213750000000002]`. The valuation components are the existing energy, hydration, fatigue and discomfort target-error reductions with weights from `PsycheState.initial_organism_v03`; no new reward exists. Each terminal state is evaluated once from its physical start-to-terminal delta. Supports remain ep

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.18.1 — Prospective Space Development

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** ```json { "1": "YES", "10": false, "11": false, "12": null, "13": "See recorded case; NOT_AVAILABLE when no case emerged", "14": "NOT_AVAILABLE unless a supported matched WAIT chain existed", "15": "Recorded action history; prospective diagnostic was never an input", "16": "NO", "17": "unsmoothed curve retained", "18": "single-seed run; use --seeds for batch", "19": "NO", "2": "NO", "20": "YES", "21": "A", "22": "prospective representation \u2192 current action selection", "3": 1000, "4": [ { "experience_count": 0, "known_depth1": 0, "known_depth2": 0, "known_depth3": 0, "locally_nonpositive_deeper_positive_count": 0, "multi_consequence_count": 0, "positive_depth1_count": 0, "positive_depth2_count": 0, "positive_depth3_count": 0, "supported_transition_count": 0, "tick": 0, "unknown_count": 0 }, { "experience_count": 99, "known_depth1": 1, "known_depth2": 1, "known_depth3": 0, "locally_nonpositive_deeper_positive_count": 0, "multi_consequence_count": 0, "positive_depth1_count": 0, "positive_depth2_count": 0, "positive_depth3_count": 0, "supported_transition_count": 12, "tick": 100, "unknown_count": 1 }, { "experience_count": 499, "known_depth1": 0, "known_depth2": 0, "known_depth3": 0, "locally_nonpositive_deeper_positive_count": 0, "multi_consequence_count": 1, "positive_depth1_count": 0, "positive_depth2_count": 0, "positive_depth3_count": 0, "supported_transition_count": 20, 

**WHAT IT MEANS:** ```json { "1": "YES", "10": false, "11": false, "12": null, "13": "See recorded case; NOT_AVAILABLE when no case emerged", "14": "NOT_AVAILABLE unless a supported matched WAIT chain existed", "15": "Recorded action history; prospective diagnostic was never an input", "16": "NO", "17": "unsmoothed curve retained", "18": "single-seed run; use --seeds for batch", "19": "NO", "2": "NO", "20": "YES", "21": "A", "22": "prospective representation \u2192 current action selection", "3": 1000, "4": [ { "experience_count": 0, "known_depth1": 0, "known_depth2": 0, "known_depth3": 0, "locally_nonpositive_deeper_positive_count": 0, "multi_consequence_count": 0, "positive_depth1_count": 0, "positive_depth2

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.18.2 — update4182 dynamic ecology

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** 1. Every matched condition began with a fresh psyche: YES. 2. Cognition changed: NO. Policy changed: NO. 3. Source effects use the existing object/world/body transition path: YES. 4. Usefulness, phase, direction, distance, resistance, and accessibility semantic leaks: ABSENT. 5. Emission is produced by the object in world space independently of the agent: YES. 6. Source opportunities/encounters/interactions are recorded per condition in `OPPORTUNITY_AUDIT.json`. 7. In the 100-tick seed-17 free validation, signal conditions produced local exposures before direct source perception; USE opportunities occurred but free policy selected no USE on OBJ-12 (`SOURCE_USED=false`). 8. Consequently, free-policy body effects from the target source, supported signal→encounter/consequence learning, prediction participation, and behavioral signal use were NULL in that short run. 9. Prospective depth was history/context dependent in free controls; positive futures from the sustaining source were not demonstrated in the short free validation. 10. Correlated and decorrelated signals differed physically; the short free validation does not establish a learned difference. 11. No previously unseen positive complete sequence emerged under free policy in the short validation. 12. Multi-seed sensitivity is enabled by `--seeds`; the canonical free control validation used seed 17. 13. Generic quantitative 

**WHAT IT MEANS:** 1. Every matched condition began with a fresh psyche: YES. 2. Cognition changed: NO. Policy changed: NO. 3. Source effects use the existing object/world/body transition path: YES. 4. Usefulness, phase, direction, distance, resistance, and accessibility semantic leaks: ABSENT. 5. Emission is produced by the object in world space independently of the agent: YES. 6. Source opportunities/encounters/interactions are recorded per condition in `OPPORTUNITY_AUDIT.json`. 7. In the 100-tick seed-17 free validation, signal conditions produced local exposures before direct source perception; USE opportunities occurred but free policy selected no USE on OBJ-12 (`SOURCE_USED=false`). 8. Consequently, free

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.19 — Context Formation × Background Prediction

**QUESTION:** - **A (guaranteed by implementation):** field evolution during WAIT; local-only ambient fragments; no WORLD_CHANGED signal; bounded store; schema multiplier. - **B (possible, not required):** free-policy behavioral change after violation; information-seeking-like moves; compositional reuse affecting choices. - **C (observed):** see JSON artifacts; NULL retained where applicable.

**CHANGE:** Continuous numeric background fields evolve every tick (including WAIT). Local `AMBIENT_SCALAR` fragments enter multi-channel perception. Bounded co-occurrence store compresses repeated quantized sensory signatures and supports partial prediction + mismatch measurement. Compositional action patterns are audited from existing legal actions only. No semantic context/curiosity/WORLD_CHANGED.

**TEST / RESULT:** Continuous numeric background fields evolve every tick (including WAIT). Local `AMBIENT_SCALAR` fragments enter multi-channel perception. Bounded co-occurrence store compresses repeated quantized sensory signatures and supports partial prediction + mismatch measurement. Compositional action patterns are audited from existing legal actions only. No semantic context/curiosity/WORLD_CHANGED. - `mechanistic_mind/world_engine/background_fields.py` (new) - `mechanistic_mind/research/background_context.py` (new) - `mechanistic_mind/research/compositional_action_patterns.py` (new) - `mechanistic_mind/world_engine/models.py` (`background_fields_spec`) - `mechanistic_mind/world_engine/engine.py` (init/advance/coupling/schema) - `mechanistic_mind/world_engine/perception.py` (`AMBIENT_SCALAR`) - `experiments/run_update419_context_formation.py` (new) - Observer preset wiring (if present in app.py) - `results/update419_context_formation/*` Multi-channel perception packet, world tick advance on WAIT, experience-gated psyche/free policy, temporal contingency (untouched), observer snapshot pattern, bounded compression ideas from experience_compression (separate store to avoid duplicate cognitive systems inside psyche for this measurement update). Background field grids; local ambient channel; bounded co-occurrence/partial prediction store; compositional action pattern audit. QUIET_WORLD, FAMILI

**WHAT IT MEANS:** Continuous numeric background fields evolve every tick (including WAIT). Local `AMBIENT_SCALAR` fragments enter multi-channel perception. Bounded co-occurrence store compresses repeated quantized sensory signatures and supports partial prediction + mismatch measurement. Compositional action patterns are audited from existing legal actions only. No semantic context/curiosity/WORLD_CHANGED. - `mechanistic_mind/world_engine/background_fields.py` (new) - `mechanistic_mind/research/background_context.py` (new) - `mechanistic_mind/research/compositional_action_patterns.py` (new) - `mechanistic_mind/world_engine/models.py` (`background_fields_spec`) - `mechanistic_mind/world_engine/engine.py` (init

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Longer free-policy post-violation runs; sensory-radius ablations on the same world; true locomotor travel between basins; transfer of stored patterns across engines without phase labels.

## EXP-4.20 — Persistent Body × Hierarchical Prediction

**QUESTION:** NOT_RECORDED

**CHANGE:** Generic persistent process variables (`internal_a`…) advance every tick including WAIT, modulated by local ambient samples and relieved by ordinary actions (EMIT). Bounded `*_signal` fragments enter interoception. A separate research store tracks local lagged associations and relations among them (no LEVEL_*/SELF cognitive objects).

**TEST / RESULT:** - Local prediction status: NO_LOCAL - Pre-signal WAIT ticks with predictive structure: 0 - Same-state tolerance: True; divergence_observed=False - Changing-body rate difference: 0.0

**WHAT IT MEANS:** - Local prediction status: NO_LOCAL - Pre-signal WAIT ticks with predictive structure: 0 - Same-state tolerance: True; divergence_observed=False - Changing-body rate difference: 0.0

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Evidence→selection not forced; full multi-seed matrix recommended; legacy suites 28–33 not re-run.

## EXP-4.21 — Provenance-Preserving Predictive Compression

**QUESTION:** NOT_RECORDED

**CHANGE:** Three timescales: bounded recent buffer; compressed predictive structures with support/EMA; exceptions + frozen prediction-at-event + bounded provenance/revision. Redundant raw_log entries are physically purged. Metrics never affect cognition. Update 4.20 deeper-in-use / presignal / history-divergence NULLs are not tuned.

**TEST / RESULT:** 1. Recent buffer bounded: YES (128). 2. Compressed store bounded: YES (64). 3. Provenance bounded: YES (24 edges/structure). 4. Redundant raw deleted: YES — see RAW_REMOVAL_AUDIT purge removed=11. 5. Scaling vs ticks (boring bytes): ticks=[1000, 5000, 10000, 25000, 50000, 100000] bytes=[37263, 37771, 37779, 38287, 38287, 38295]. 6. Novelty vs boring last bytes: novelty=101409 boring=38295. 7–8. Prediction preserved after compression/deletion: True. 9. Rare structured retained (probe): True. 10. Rare random exceptions counted: 32 (no permanence guarantee). 11–12. PAE reconstructable after deletion: True (frozen, not retrodiction). 13–14. Revision from ordinary mismatch: YES; chains bounded depth 8. 15–16. Representatives expandable: YES; effect on cognition not claimed (NULL OK). 17. Same-present/different-history different_predictions=False different_provenance=False. 18–19. Reactivation=True; forgotten_count=737. 20–23. 4.19 integration patterns=2 mismatches=7; 4.20 locals=73 relations=0. 24. 4.20 NULL accidentally positive: NO ({'deeper_in_use_not_acceptance_target': True, 'presignal_not_tuned': True, 'history_divergence_not_tuned': True}). 25–26. Semantic/GT leak: NO. 27. Category A: capacities, purge, PAE freeze, observer expand, metrics not in selection. 28. Category B: strong sublinear boring compression; reactivation; history-dependent provenance. 29. Category C: see JSO

**WHAT IT MEANS:** 1. Recent buffer bounded: YES (128). 2. Compressed store bounded: YES (64). 3. Provenance bounded: YES (24 edges/structure). 4. Redundant raw deleted: YES — see RAW_REMOVAL_AUDIT purge removed=11. 5. Scaling vs ticks (boring bytes): ticks=[1000, 5000, 10000, 25000, 50000, 100000] bytes=[37263, 37771, 37779, 38287, 38287, 38295]. 6. Novelty vs boring last bytes: novelty=101409 boring=38295. 7–8. Prediction preserved after compression/deletion: True. 9. Rare structured retained (probe): True. 10. Rare random exceptions counted: 32 (no permanence guarantee). 11–12. PAE reconstructable after deletion: True (frozen, not retrodiction). 13–14. Revision from ordinary mismatch: YES; chains bounded de

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.22 — Emergent Multi-Scale Predictive Organization

**QUESTION:** Not asserted unless causal chain fully supported. Smoke default: report observations only.

**CHANGE:** Bounded local structures → co-occurrence relations → candidate broader structures with depth safety cap (not a semantic hierarchy). Local-only vs broader-conditioned prediction compared researcher-side. Selective ablations. Integrates 4.21 purge/PAE. No LEVEL_*/REGIME/G labels in cognition. 4.20/4.21 NULLs not acceptance targets.

**TEST / RESULT:** 1. Local predictive structures form: **True** 2. Relations among local structures form: **True** 3. Candidate broader structures form: **True** 4. Derived only from agent-available learned evidence: **YES** (GT G never ingested) 5. Additional predictive value: **True** (see PREDICTIVE_VALUE.json) 6. Predictive delta magnitudes: [0.28749503858376424, 0.00443535994549632, 0.007828524364886402, -0.0002998865344917001, 0.006232502223225356] 7. Matched local / different broader histories different predictions: **True** 8. Selective broader ablation removes difference: **False** 9. Local prediction survives broader ablation: see BROADER_ABLATION / matrix local status 10. Local ablation: predictions → NO_LOCAL when ablate_local 11. Relation ablation: relations cleared; broader may still exist from prior formation 12. Shuffled history: see matrix shuffle snaps vs common 13. Desynchronization: see matrix desync 14. Independent matched-marginal: see matrix independent 15. Random cluster control: see matrix random_cluster (compare deltas) 16. Broader survived raw-history purge context: **True** 17. Provenance preserved: YES (bounded; ablatable) 18. Silent physical change revised broader: revision_events=120 19. Historical PAE preserved through revision/purge: **True** 20. Novel local transfer broader used: **False** 21. Recursive depth > 0 candidates: see depth_distribution in snaps 22. D

**WHAT IT MEANS:** 1. Local predictive structures form: **True** 2. Relations among local structures form: **True** 3. Candidate broader structures form: **True** 4. Derived only from agent-available learned evidence: **YES** (GT G never ingested) 5. Additional predictive value: **True** (see PREDICTIVE_VALUE.json) 6. Predictive delta magnitudes: [0.28749503858376424, 0.00443535994549632, 0.007828524364886402, -0.0002998865344917001, 0.006232502223225356] 7. Matched local / different broader histories different predictions: **True** 8. Selective broader ablation removes difference: **False** 9. Local prediction survives broader ablation: see BROADER_ABLATION / matrix local status 10. Local ablation: prediction

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.23 — Prospective Trajectory Composition

**QUESTION:** - Novel prospective trajectory composition: **ASSERTED** - Distal action influence: **NOT ASSERTED** - Candidate online replanning: **NOT ASSERTED**

**CHANGE:** Bounded composition over learned action-conditioned transitions only. No world-engine lookahead, no GOAL/PLAN/TARGET, no delayed-reward bonus. Exposure audit for complete sequences. Historical 4.20/4.21/4.22 NULLs preserved.

**TEST / RESULT:** 1. One-step prediction functional: **YES** 2. Component transitions learned: **YES** 3. Critical complete trajectory in novel: **NO** 4. full_sequence_exposure_count: {'17': 0, '23': 0, '41': 0, '59': 0, '83': 0} 5. Novel multi-step composition: **True** seeds=['17', '23', '41', '59', '83'] 6-7. Horizon: see HORIZON_SCALING.json 8. Broken-link blocks novel: **True** 9. Shuffled: per-seed 10. Cached vs novel: artifacts 11. Composition ablation removes: **True** 12. One-step survives: **True** 13-16. Relations/broader: not required; see ablation JSONs 17-19. Alternatives/WAIT/conflict: artifacts 20-21. Distal action influence: per-seed; ablation compares choices 22-28. Silent/interrupt/branch/swap/transfer/purge/provenance: artifacts 29-33. Same-present history diagnostic; 4.22 unexplained path remains 34-37. Body/structured/bounds: artifacts 38. Future GT leak: NO 39. Planning leak: [] 40. New rewards: NO 41-45. Integrations + historical NULLs preserved 46. Category A: bounds, audit, ablations, no planning tokens 47. Category B: novel composition, distal influence, transfer 48. Category C: JSON only 49. NULLs: seeds without novel success; no online-replanning claim 50. First unsupported arrow: **distal prediction -> current action as psyche faculty (researcher proxy only; not claimed)**

**WHAT IT MEANS:** 1. One-step prediction functional: **YES** 2. Component transitions learned: **YES** 3. Critical complete trajectory in novel: **NO** 4. full_sequence_exposure_count: {'17': 0, '23': 0, '41': 0, '59': 0, '83': 0} 5. Novel multi-step composition: **True** seeds=['17', '23', '41', '59', '83'] 6-7. Horizon: see HORIZON_SCALING.json 8. Broken-link blocks novel: **True** 9. Shuffled: per-seed 10. Cached vs novel: artifacts 11. Composition ablation removes: **True** 12. One-step survives: **True** 13-16. Relations/broader: not required; see ablation JSONs 17-19. Alternatives/WAIT/conflict: artifacts 20-21. Distal action influence: per-seed; ablation compares choices 22-28. Silent/interrupt/branch/

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.24 — Body as Endogenous Temporal Reference

**QUESTION:** NOT_RECORDED

**CHANGE:** State-only vs trajectory-conditioned prediction over ordinary body fragments (internal_a/b, load_c, exchange_d). No CLOCK/ELAPSED_TIME/AGE. Simulator ticks and wall-clock are researcher metrics only. Uses 4.20 persistent process physics with rate/days knobs.

**TEST / RESULT:** 1. Explicit clock present: **NO** 2. Tick identity in cognition: **NO** 3. Wall-clock in cognition: **NO** (control: bodies identical under delay) 4. Body-rate manip changes body paths at matched ticks: **True** 5. Stable world / changing body: prediction available - see artifact 6. Changing world / stable body: see artifact 7. Same ticks different body: finals differ **True** 8. Diff ticks similar body: see DIFF_TICKS_SIM_BODY.json 9. Same state diff history traj preds differ seeds: [] 10. Return-to-state restores same predictive state: per-seed return_same_pred 11. Trajectory vs state: traj_helps seeds=[] 12. Scale generalization: SCALE_GENERALIZATION.json 13. Wall-clock control bodies identical: **True** 14. Integrations 4.19-4.23: hooks intact; historical NULLs preserved 15. Category A: no clock tokens; measurable state vs traj; ablations; researcher metrics separate 16. Category B: traj improves prediction; history-conditioned divergence; rate-following prediction 17. Category C: numbers above / JSON 18. Strong endogenous temporal reference claim: **NOT ASSERTED** 19. Feeling/subjective time claimed: **NO** 20. First unsupported causal arrow: **same body state + different history -> different prediction (NULL)**

**WHAT IT MEANS:** 1. Explicit clock present: **NO** 2. Tick identity in cognition: **NO** 3. Wall-clock in cognition: **NO** (control: bodies identical under delay) 4. Body-rate manip changes body paths at matched ticks: **True** 5. Stable world / changing body: prediction available - see artifact 6. Changing world / stable body: see artifact 7. Same ticks different body: finals differ **True** 8. Diff ticks similar body: see DIFF_TICKS_SIM_BODY.json 9. Same state diff history traj preds differ seeds: [] 10. Return-to-state restores same predictive state: per-seed return_same_pred 11. Trajectory vs state: traj_helps seeds=[] 12. Scale generalization: SCALE_GENERALIZATION.json 13. Wall-clock control bodies ide

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.25 — Emergent Instrumental Observation

**QUESTION:** - C1 acquired physical observability: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2 learned predictive use: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3 self-initiated instrumental interaction: **NOT ASSERTED** - Novel mediated prospective composition: **ASSERTED**

**CHANGE:** Physical transduction W->M->BODY only. No TOOL/INFORMATION/EPISTEMIC rewards. C1/C2/C3 evaluated independently. Preserves 4.23 distal->action NULL and 4.24 temporal NULL.

**TEST / RESULT:** Physical transduction W->M->BODY only. No TOOL/INFORMATION/EPISTEMIC rewards. C1/C2/C3 evaluated independently. Preserves 4.23 distal->action NULL and 4.24 temporal NULL. - `mechanistic_mind/research/instrumental_observation.py` - `experiments/run_update425_instrumental_observation.py` - Observer `4.25 Instrumental Observation` - `results/update425_instrumental_observation/*` - seed 17: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - seed 23: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - seed 41: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - seed 59: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - seed 83: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - C1 acquired physical observability: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2 learned predictive

**WHAT IT MEANS:** Physical transduction W->M->BODY only. No TOOL/INFORMATION/EPISTEMIC rewards. C1/C2/C3 evaluated independently. Preserves 4.23 distal->action NULL and 4.24 temporal NULL. - `mechanistic_mind/research/instrumental_observation.py` - `experiments/run_update425_instrumental_observation.py` - Observer `4.25 Instrumental Observation` - `results/update425_instrumental_observation/*` - seed 17: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=True novel=False broken=False one_step=True - seed 23: C1=True class=STRICT_ACQUIRED_OBSERVABILITY C2=True C2_useless=False C3_proxy_change=True prospective_full_exp=0 mediated_to_F=T

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.26 — Prospective Consequence Influence

**QUESTION:** - C1_distal_prospective_representation: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_present_action_association: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_causal_distal_consequence_influence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_online_consequence_revision_of_action: **NOT ASSERTED** seeds=[]

**CHANGE:** 4.23 composition + existing ordinary_state_value (4.5/4.18) blended into softmax action sampling (NOT argmax; NOT goal/desire). Distal blend gated by composition. Preserves historical NULLs for 4.23 distal->action until C3 asserted here.

**TEST / RESULT:** 4.23 composition + existing ordinary_state_value (4.5/4.18) blended into softmax action sampling (NOT argmax; NOT goal/desire). Distal blend gated by composition. Preserves historical NULLs for 4.23 distal->action until C3 asserted here. { "CATEGORY_A": [ "existing ordinary_state_value / prospective_ordinary_value reused", "4.23 distal_prediction reused", "softmax stochastic selection (not argmax)" ], "CATEGORY_B": [ "distal ordinary value may blend into logits when composition available" ], "NOT_IMPLEMENTED": [ "GOAL", "TARGET", "DESIRE", "WANT", "WANT_NOT", "PREFERENCE", "FUTURE_PREFERENCE", "PLAN", "STRATEGY", "INTENTION", "PURPOSE", "AVOID", "SEEK", "FEAR", "HOPE", "EXPECTED_REWARD", "FUTURE_REWARD", "DISCOUNTED_REWARD", "VALUE_FUNCTION", "UTILITY" ], "DISTAL_BLEND": 0.55, "DEFAULT_TEMPERATURE": 1.25 } - seed 17: expA=0 expB=0 A_comp=True B_comp=True vals_differ=True shift_B=0.2275 delta_B=0.1000 comp_ablate_1step=True swap_pred=False swap_act=True - seed 23: expA=0 expB=0 A_comp=True B_comp=True vals_differ=True shift_B=0.1600 delta_B=0.0850 comp_ablate_1step=True swap_pred=False swap_act=False - seed 41: expA=0 expB=0 A_comp=True B_comp=True vals_differ=True shift_B=0.1775 delta_B=0.0600 comp_ablate_1step=True swap_pred=False swap_act=True - seed 59: expA=0 expB=0 A_comp=True B_comp=True vals_differ=True shift_B=0.0825 delta_B=0.0125 comp_ablate_1step=True swap_pred=False

**WHAT IT MEANS:** 4.23 composition + existing ordinary_state_value (4.5/4.18) blended into softmax action sampling (NOT argmax; NOT goal/desire). Distal blend gated by composition. Preserves historical NULLs for 4.23 distal->action until C3 asserted here. { "CATEGORY_A": [ "existing ordinary_state_value / prospective_ordinary_value reused", "4.23 distal_prediction reused", "softmax stochastic selection (not argmax)" ], "CATEGORY_B": [ "distal ordinary value may blend into logits when composition available" ], "NOT_IMPLEMENTED": [ "GOAL", "TARGET", "DESIRE", "WANT", "WANT_NOT", "PREFERENCE", "FUTURE_PREFERENCE", "PLAN", "STRATEGY", "INTENTION", "PURPOSE", "AVOID", "SEEK", "FEAR", "HOPE", "EXPECTED_REWARD", "FU

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.27 — Predictive Generalization

**QUESTION:** - C1_shared_predictive_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_novel_instance_predictive_generalization: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_generalized_action_influence_via_4_26: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_experience_driven_revision_on_counterexample: **ASSERTED** seeds=['17', '23', '41', '59', '83']

**CHANGE:** Physical feature conjunction store (exact / single / pair). No CATEGORY/CLASS/CONCEPT/THREAT. Novel instance {a,b,f} probed with exposure_exact=0. Optional C3 via unchanged 4.26 ordinary_state_value + action_logits. C4 via observe() on counterexample only — no EMA retune.

**TEST / RESULT:** Physical feature conjunction store (exact / single / pair). No CATEGORY/CLASS/CONCEPT/THREAT. Novel instance {a,b,f} probed with exposure_exact=0. Optional C3 via unchanged 4.26 ordinary_state_value + action_logits. C4 via observe() on counterexample only — no EMA retune. - C1_shared_predictive_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_novel_instance_predictive_generalization: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_generalized_action_influence_via_4_26: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_experience_driven_revision_on_counterexample: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - seed 17: C1=True C2=True C3=True C4=True novel_exp=0 status=SHARED l1F-=3.885780586188048e-16 - seed 23: C1=True C2=True C3=True C4=True novel_exp=0 status=SHARED l1F-=3.885780586188048e-16 - seed 41: C1=True C2=True C3=True C4=True novel_exp=0 status=SHARED l1F-=3.885780586188048e-16 - seed 59: C1=True C2=True C3=True C4=True novel_exp=0 status=SHARED l1F-=3.885780586188048e-16 - seed 83: C1=True C2=True C3=True C4=True novel_exp=0 status=SHARED l1F-=3.885780586188048e-16 - 4.26 C4 remains NOT ASSERTED (not retuned here). - 4.25 C3 remains NOT ASSERTED. - Prior FINAL_REPORTs untouched.

**WHAT IT MEANS:** Physical feature conjunction store (exact / single / pair). No CATEGORY/CLASS/CONCEPT/THREAT. Novel instance {a,b,f} probed with exposure_exact=0. Optional C3 via unchanged 4.26 ordinary_state_value + action_logits. C4 via observe() on counterexample only — no EMA retune. - C1_shared_predictive_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_novel_instance_predictive_generalization: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_generalized_action_influence_via_4_26: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_experience_driven_revision_on_counterexample: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - seed 17: C1=True C2=True C3=True C4=True novel_ex

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.28 — Competing Predictive Continuations

**QUESTION:** - C1_simultaneous_competing_predictive_continuations: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_history_dependent_action_influence: **NOT ASSERTED** seeds=[] partial_seeds=[] - C3_evidence_driven_behavioral_transition: **NOT ASSERTED** seeds=[] - C4_history_dependent_hysteresis: **NOT ASSERTED** seeds=[]

**CHANGE:** Existing 4.23 composition + 4.26 ordinary_state_value → softmax. No HABIT/BELIEF/COMMITMENT/CONFIDENCE/ENTRENCHMENT/SWITCHING_COST in cognition. Historical support = ordinary learn_transition / full_sequence exposure counts.

**TEST / RESULT:** Existing 4.23 composition + 4.26 ordinary_state_value → softmax. No HABIT/BELIEF/COMMITMENT/CONFIDENCE/ENTRENCHMENT/SWITCHING_COST in cognition. Historical support = ordinary learn_transition / full_sequence exposure counts. - C1_simultaneous_competing_predictive_continuations: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_history_dependent_action_influence: **NOT ASSERTED** seeds=[] partial_seeds=[] - C3_evidence_driven_behavioral_transition: **NOT ASSERTED** seeds=[] - C4_history_dependent_hysteresis: **NOT ASSERTED** seeds=[] - seed 17: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - seed 23: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - seed 41: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - seed 59: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - seed 83: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - 4.25 C3 NULL, 4.26 C4 NULL untouched; no EMA retune. - 4.26 C3 / 4.27 C1–C4 preserved as historical ASSERTED. - Prior FINAL_REPORTs not rewritten. Under the unchanged 4.26 pathway, action logits depend on immediate + distal ordinary_state_value of composed predictions 

**WHAT IT MEANS:** Existing 4.23 composition + 4.26 ordinary_state_value → softmax. No HABIT/BELIEF/COMMITMENT/CONFIDENCE/ENTRENCHMENT/SWITCHING_COST in cognition. Historical support = ordinary learn_transition / full_sequence exposure counts. - C1_simultaneous_competing_predictive_continuations: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_history_dependent_action_influence: **NOT ASSERTED** seeds=[] partial_seeds=[] - C3_evidence_driven_behavioral_transition: **NOT ASSERTED** seeds=[] - C4_history_dependent_hysteresis: **NOT ASSERTED** seeds=[] - seed 17: history_dependent_action_distribution C1=True C2=False C2part=False C3=False C4=False trans=no_transition - seed 23: history_dependent_action_dis

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.29 — Predictive Reliability

**QUESTION:** - C1_multiple_outcome_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_matched_expected_consequence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_distributional_action_influence: **NOT ASSERTED** seeds=[] - C4_selective_causal_dependence: **NOT ASSERTED** seeds=[] - C5_experience_driven_reliability_reversal: **NOT ASSERTED** seeds=[]

**CHANGE:** No new cognition variables. Existing 4.23 transitions retain mean + var_sum; pc.reliability(row) is computed on one-step predictions but is NOT consumed by 4.26 action_logits (scalar ordinary_value of mean predicted_distal only). DISTAL_BLEND / T unchanged. No variance/reliability term added to force C3.

**TEST / RESULT:** No new cognition variables. Existing 4.23 transitions retain mean + var_sum; pc.reliability(row) is computed on one-step predictions but is NOT consumed by 4.26 action_logits (scalar ordinary_value of mean predicted_distal only). DISTAL_BLEND / T unchanged. No variance/reliability term added to force C3. MATCHED_MEAN_TOLERANCE = 0.02 (pre-registered). ACTION_DELTA_TOL = 0.03. A: 90/10 mid_hi/mid_lo; B: 50/50 extremes calibrated to matched channel mean. full_sequence_exposure_count = 0 for both chains. - C1_multiple_outcome_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_matched_expected_consequence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_distributional_action_influence: **NOT ASSERTED** seeds=[] - C4_selective_causal_dependence: **NOT ASSERTED** seeds=[] - C5_experience_driven_reliability_reversal: **NOT ASSERTED** seeds=[] - seed 17: matched=True dV=0.0 varA=0.0 varB=0.0378787878787879 dP=0.0 C1=True C2=True C3=False first=differential_present_action_selection 426_alive=True - seed 23: matched=True dV=0.0 varA=0.0 varB=0.0378787878787879 dP=0.0 C1=True C2=True C3=False first=differential_present_action_selection 426_alive=True - seed 41: matched=True dV=0.0 varA=0.0 varB=0.0378787878787879 dP=0.0 C1=True C2=True C3=False first=differential_present_action_selection 426_alive=True - seed 59: matched=True dV=0.0 varA=0.0 varB=0.0378787878787879 d

**WHAT IT MEANS:** No new cognition variables. Existing 4.23 transitions retain mean + var_sum; pc.reliability(row) is computed on one-step predictions but is NOT consumed by 4.26 action_logits (scalar ordinary_value of mean predicted_distal only). DISTAL_BLEND / T unchanged. No variance/reliability term added to force C3. MATCHED_MEAN_TOLERANCE = 0.02 (pre-registered). ACTION_DELTA_TOL = 0.03. A: 90/10 mid_hi/mid_lo; B: 50/50 extremes calibrated to matched channel mean. full_sequence_exposure_count = 0 for both chains. - C1_multiple_outcome_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_matched_expected_consequence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_distributional_actio

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Only if a future update introduces a generic pathway that preserves distributional structure into action WITHOUT semantic uncertainty — or investigate information- seeking under unavoidable physical evolution (explicitly deferred by 4.29 §22).

## EXP-4.30 — Unavoidable State Transition

**QUESTION:** - C1_continuing_physical_evolution_under_WAIT: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_passive_acquisition_of_new_accessible_evidence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_evidence_driven_prediction_revision: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_revised_prediction_to_revised_action: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_complete_continuing_world_loop: **ASSERTED** seeds=['17', '23', '41', '59', '83']

**CHANGE:** WAIT = no active intervention. Autonomous field + body continue evolving. No UNCERTAINTY/URGENCY/WAIT_COST/DELIBERATION. No EMA retune. No variance in logits. Online revision via ordinary learn_transition on field-conditioned distal outcomes. Action via unchanged 4.26 ordinary_state_value → softmax.

**TEST / RESULT:** WAIT = no active intervention. Autonomous field + body continue evolving. No UNCERTAINTY/URGENCY/WAIT_COST/DELIBERATION. No EMA retune. No variance in logits. Online revision via ordinary learn_transition on field-conditioned distal outcomes. Action via unchanged 4.26 ordinary_state_value → softmax. NOT pause/freeze/deliberate. Physical field_rate advances; body metabolizes. Frozen-world control sets freeze_field=True for comparison only. - C1_continuing_physical_evolution_under_WAIT: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_passive_acquisition_of_new_accessible_evidence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_evidence_driven_prediction_revision: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_revised_prediction_to_revised_action: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_complete_continuing_world_loop: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - seed 17: fieldΔ=0.600 valΔB=0.8347999999999999 ΔP_B=0.0799 C1=True C2=True C3=True C4=True C5=True first=NONE_ALL_SUPPORTED - seed 23: fieldΔ=0.600 valΔB=0.8347999999999999 ΔP_B=0.0799 C1=True C2=True C3=True C4=True C5=True first=NONE_ALL_SUPPORTED - seed 41: fieldΔ=0.600 valΔB=0.8347999999999999 ΔP_B=0.0799 C1=True C2=True C3=True C4=True C5=True first=NONE_ALL_SUPPORTED - seed 59: fieldΔ=0.600 valΔB=0.8347999999999999 ΔP_B=0.0799 C1=True C2=True C3=True C4=True C5=True first=

**WHAT IT MEANS:** WAIT = no active intervention. Autonomous field + body continue evolving. No UNCERTAINTY/URGENCY/WAIT_COST/DELIBERATION. No EMA retune. No variance in logits. Online revision via ordinary learn_transition on field-conditioned distal outcomes. Action via unchanged 4.26 ordinary_state_value → softmax. NOT pause/freeze/deliberate. Physical field_rate advances; body metabolizes. Frozen-world control sets freeze_field=True for comparison only. - C1_continuing_physical_evolution_under_WAIT: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_passive_acquisition_of_new_accessible_evidence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_evidence_driven_prediction_revision: **ASSERTED** se

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Evidence-producing active action → discriminating evidence → revision → later action (connect 4.25 observability with continuing-world revision) — not implemented here.

## EXP-4.31 — Evidence-Producing Physical Action

**QUESTION:** - C1_action_caused_observability_change: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_action_produced_discriminating_evidence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_evidence_to_prediction_revision: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_revision_to_later_action_change: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_forced_closed_loop: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C6_autonomous_mediator_action_preference: **NOT ASSERTED** seeds=[] - C7_evidence_dependent_autonomous_selection: **NOT ASSERTED** seeds=[]

**CHANGE:** Reuses 4.25 WORLD→MEDIATOR→BODY transduction (`instrumental_observation`). Physical action name: CONTACT_M (not OBSERVE/INSPECT). Forced chain: CONTACT_M → mediated signal → io.predict revision → revise later distal via learn_transition → 4.26 action_logits. Free selection: CONTACT_M / PUSH_X / WAIT with matched immediate costs only — no information-gain term (preserves 4.29 NULL).

**TEST / RESULT:** **Outcome A (forced pass / autonomous fail):** An ordinary physical action (CONTACT_M) can produce discriminating evidence that revises prediction and changes subsequent A/B behavior when CONTACT_M is externally selected — but the tested architecture does **not** autonomously favor CONTACT_M because of that evidence-producing consequence. Matched immediate costs: CONTACT_M ≈ PUSH_X ≈ same ordinary_state_value → equal softmax mass. No pathway assigns present value to: CONTACT_M → future evidence → revision → later better action

**WHAT IT MEANS:** **Outcome A (forced pass / autonomous fail):** An ordinary physical action (CONTACT_M) can produce discriminating evidence that revises prediction and changes subsequent A/B behavior when CONTACT_M is externally selected — but the tested architecture does **not** autonomously favor CONTACT_M because of that evidence-producing consequence. Matched immediate costs: CONTACT_M ≈ PUSH_X ≈ same ordinary_state_value → equal softmax mass. No pathway assigns present value to: CONTACT_M → future evidence → revision → later better action

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Only if a future generic (non-semantic) pathway can assign present value to actions whose benefit is mediated by future evidence→revision→later action. Do not bridge with expected information gain.

## EXP-4.32 — Learning-Mediated Futures

**QUESTION:** - C1_endogenous_predictive_state_transition: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_predictive_transition_causes_later_action: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_learning_mediated_distal_consequence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_prospective_representation_of_learning_mediated_future: **NOT ASSERTED** seeds=[] - C5_learning_mediated_present_action_value: **NOT ASSERTED** seeds=[] - C6_novel_composition_of_learning_mediated_future: **NOT ASSERTED** seeds=[] - C7_autonomous_CONTACT_M_selection: **NOT ASSERTED** seeds=[] - C8_revision_dependent_autonomous_selection: **NOT ASSERTED** seeds=[]

**CHANGE:** No INFORMATION/CURIOSITY/LEARNING_VALUE. Reuses 4.25/4.26/4.31 machinery. Does not serialize predictive memory as a sensor. Does not inject counterfactual F into CONTACT_M logits (forbidden bridge).

**TEST / RESULT:** Expected Outcome A: C1–C3 pass; C4 fails. Downstream learning-mediated physical loop works when CONTACT_M is forced, but prospective machinery cannot represent revision-gated later action choice, and present CONTACT_M value remains immediate-only (FULL == REVISION-OFF).

**WHAT IT MEANS:** Expected Outcome A: C1–C3 pass; C4 fails. Downstream learning-mediated physical loop works when CONTACT_M is forced, but prospective machinery cannot represent revision-gated later action choice, and present CONTACT_M value remains immediate-only (FULL == REVISION-OFF).

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Only if a future generic (non-semantic) representation can treat endogenous predictive-organization transitions as first-class nodes in prospective composition — without info-gain rewards or self-model sensors.

## EXP-4.33 — Acquired Conditional Prospection

**QUESTION:** - C1_acquired_state_conditional_later_action: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_multiple_prospective_physical_continuations: **NOT ASSERTED** seeds=[] - C3_continuation_specific_action_propagation: **NOT ASSERTED** seeds=[] - C4_conditional_prospective_branching: **NOT ASSERTED** seeds=[] - C5_conditional_future_to_present_a0_value: **NOT ASSERTED** seeds=[] - C6_novel_contingent_composition: **NOT ASSERTED** seeds=[] - C7_structured_vs_unstructured: **NOT ASSERTED** seeds=[]

**CHANGE:** - fixed_sequence: pc.distal_prediction(store, start, action_seq) and compose_trajectories expand a pre-specified action list / branch_actions; they do not select later actions via ordinary_state_value on predicted future fragments. - mean_collapse: pc.learn_transition keys by (quantized_antecedent, action) and stores one mean consequent; A0->Ox and A0->Oy from the same S0 collapse. - relation_to_432: 4.32 C4 NULL: composition could chain CONTACT_M + pre-specified A/B but could not represent revision-gated A-vs-B. 4.33 removes learning mediation and tests the more primitive physical contingent future.

**TEST / RESULT:** C1 passes; C2 fails — reactive conditional action works; prospection cannot retain multiple discrete physical continuations (mean collapse).

**WHAT IT MEANS:** C1 passes; C2 fails — reactive conditional action works; prospection cannot retain multiple discrete physical continuations (mean collapse).

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If multi-continuation retention is desired, a generic (non-semantic) mixture/ multi-mode consequent store would be needed before contingent action propagation into present A0 value — without adding planners or info-gain.

## EXP-4.34 — Bounded Multimodal Consequence Learning

**QUESTION:** - C1_unimodal_compression: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_bimodal_consequence_retention: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_multimodal_generality: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_structure_beyond_mean_variance: **NOT ASSERTED** seeds=[] - C5_online_mode_formation: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C6_online_revision_disappearance: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C7_boundedness: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C8_raw_history_independence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C9_empirical_weight_retention: **ASSERTED** seeds=['17', '23', '41', '59', '83']

**CHANGE:** { "legacy_storage": "pc.learn_transition: one mean (sum/n) + var_sum per (antecedent, action)", "variance_already": "var_sum/reliability (4.29) \u2014 not multiple centers; reliability -X-> action", "raw_observations": "bounded exposure_log (256), not full archive", "elsewhere_multimodal": "4.14 multiple_consequences on tc body-deltas; not wired into pc", "bounded_memory_reuse": "pc.MAX_TRANSITIONS; 4.14 lowest-support replace; 4.21 structures", "smallest_change": "learn_transition_mm + components[] on row; predict_components additive; no action wiring", "relation_to_433": "4.33 C2 NULL from mean collapse; 4.34 tests component retention only", "params": { "MAX_COMPONENTS": 4, "ASSIGN_RADIUS_FLOOR": 0.08, "ASSIGN_SPREAD_MULT": 2.5, "MIN_COMPONENT_SUPPORT": 3.0, "IDLE_SUPPORT_DECAY": 0.995 } }

**TEST / RESULT:** Bimodal retention works, but matched broad unimodal noise also fragments into multiple persistent components — structure-beyond-mean/variance NOT established.

**WHAT IT MEANS:** Bimodal retention works, but matched broad unimodal noise also fragments into multiple persistent components — structure-beyond-mean/variance NOT established.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If C4 can be addressed with a generic (non-retuned-to-fixture) criterion that resists noise fragmentation, then a separate update: multimodal prospective propagation × continuation-specific action — without info-gain or planners. If keeping C4 NULL: first improve structure-vs-noise discrimination before revisiting 4.33.

## EXP-4.35 — Predictive Structure Selection

**QUESTION:** - C1_future_predictive_component_association: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_persistent_regime_predictive_contribution: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_iid_noise_rejection: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_memoryless_multimodal_distinction: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_structure_beyond_mean_variance: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C6_continuous_drift_control: **NOT ASSERTED** seeds=[] - C7_same_present_different_history: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C8_history_irrelevance_control: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C9_online_formation: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C10_online_dissolution: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C11_boundedness: **ASSERTED** seeds=['17', '23', '41', '59', '83']

**CHANGE:** { "after_assignment": "4.34 components: id/center/support/spread; legacy mean intact", "smallest_change": "bounded follow_by_component + follow_by_context; prequential predict", "no_retune": { "MAX_COMPONENTS": 4, "ASSIGN_RADIUS_FLOOR": 0.08 }, "bounded": { "MAX_FOLLOW_KEYS": 64, "HISTORY_LEN": 2, "MAX_CTX_FOLLOW": 64 }, "relation_434_C4": "historical geometric C4 NULL preserved; 4.35 tests predictive contribution" }

**TEST / RESULT:** Sequential predictive contribution distinguishes persistent regimes from iid/memoryless mixture, but continuous drift is also organized into apparently predictive discrete components (C6 NULL).

**WHAT IT MEANS:** Sequential predictive contribution distinguishes persistent regimes from iid/memoryless mixture, but continuous drift is also organized into apparently predictive discrete components (C6 NULL).

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If C6 addressed with a generic continuous-vs-discrete criterion, then multimodal prospective propagation × continuation-specific action (revisit 4.33). Do not implement that here.

## EXP-4.36 — Predictive Representation Sufficiency

**QUESTION:** - C1_compact_continuous_prediction: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_nonlinear_continuous_generality: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_variable_rate_continuous_generality: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_redundant_component_distinction: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_necessary_discrete_distinction: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C6_same_present_different_history: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C7_history_redundancy_control: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C8_memoryless_multimodal_separation: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C9_smoothness_failure_control: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C10_piecewise_smooth_structure: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C11_online_complexification: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C12_online_simplification: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C13_boundedness: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C14_raw_history_independence: **ASSERTED** seeds=['17', '23', '41', '59', '83']

**CHANGE:** { "layers": { "A_distributional": "4.34 components[] on transition row", "B_sequential": "4.35 follow_by_component / follow_marginal", "C_context": "4.35 follow_by_context (HISTORY_LEN=2)", "D_compact_relational": "4.36 bounded IDW anchors (x -> next mean)" }, "drift_redundancy": "Under smooth drift, 4.35 component identity carries local continuity; R2 can express the same local map without treating component id as essential.", "compression_421": "4.21 compresses event/structures; not a continuous x->next map.", "smallest_change": "Additive relational_anchors + compete_representations; 4.34/4.35 untouched.", "params": { "MAX_ANCHORS": 12, "ANCHOR_MERGE_RADIUS": 0.06, "IDW_K": 3, "EQUAL_ERR_TOL": 0.005, "MATERIAL_LOSS": 0.01, "434_unchanged": { "MAX_COMPONENTS": 4, "ASSIGN_RADIUS_FLOOR": 0.08, "ASSIGN_SPREAD_MULT": 2.5 } } }

**TEST / RESULT:** All major claims pass under tested conditions.

**WHAT IT MEANS:** All major claims pass under tested conditions.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If C1–C9/C5 hold robustly: multimodal prospective propagation × continuation-specific action.

## EXP-4.37 — Multimodal Prospective Propagation

**QUESTION:** - C1_multimodal_one_step_prospective_access: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C2_multimodal_distal_propagation: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C3_fictitious_mean_avoidance: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C4_empirical_weight_retention: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C5_predictive_structure_selectivity: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C6_same_present_different_history: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C7_history_irrelevance_control: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C8_continuation_specific_later_action: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C9_contingent_distal_consequence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C10_novel_complete_contingent_composition: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C11_world_autonomous_prospection: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C12_future_world_body_interaction: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C13_body_autonomous_prospection: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C14_mixed_causal_trajectory: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C15_online_continuation_revision: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C16_boundedness: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C17_raw_history_independence: **ASSERTED** seeds=['17', '23', '41', '59', '83'] - C18_present_action_influence: **NOT ASSERTED** seeds=[]

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Contingent + world/body-autonomous prospection work; present action influence NOT ASSERTED.

**WHAT IT MEANS:** Contingent + world/body-autonomous prospection work; present action influence NOT ASSERTED.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If C1-C17 pass: Contingent future consequence × present action influence (separate update).

## EXP-4.38 — Psyche Incubation

**QUESTION:** NOT_RECORDED

**CHANGE:** No route existed from passively acquired predictive structure to present action independent of inherited `ordinary_state_value`, and the legacy value route itself expects action-conditioned consequences. No new route was added. The native non-WAIT source is stochastic sensorimotor variation.

**TEST / RESULT:** No route existed from passively acquired predictive structure to present action independent of inherited `ordinary_state_value`, and the legacy value route itself expects action-conditioned consequences. No new route was added. The native non-WAIT source is stochastic sensorimotor variation.

**WHAT IT MEANS:** No route existed from passively acquired predictive structure to present action independent of inherited `ordinary_state_value`, and the legacy value route itself expects action-conditioned consequences. No new route was added. The native non-WAIT source is stochastic sensorimotor variation.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.39 — Intrinsic Sensorimotor Dynamics

**QUESTION:** NOT_RECORDED

**CHANGE:** The native 4.38 probability of 0.08 is a body-independent stochastic baseline sampled at research action selection. No existing bounded intermediate layer accepted actual body physics and produced motor output, and no value-free path allowed a predicted body state to enter such a layer. Update 4.39 added the smallest generic substrate: three bounded competing channels with decay, persistence, mixed actual-body coupling, bounded sensory perturbation, and stochastic motor emission. It contains no predicted-state input and does not call `ordinary_state_value` or legacy action logits.

**TEST / RESULT:** **Reactive body modulation observed; anticipatory sensorimotor modulation not observed.** Across seeds 17, 23, 41, 59, and 83: - C1–C12: **ASSERTED**. - C13–C17: **NOT ASSERTED**. - C18: **ASSERTED**. - C19: **NOT ASSERTED**. - C20–C21: **ASSERTED**.

**WHAT IT MEANS:** **Reactive body modulation observed; anticipatory sensorimotor modulation not observed.** Across seeds 17, 23, 41, 59, and 83: - C1–C12: **ASSERTED**. - C13–C17: **NOT ASSERTED**. - C18: **ASSERTED**. - C19: **NOT ASSERTED**. - C20–C21: **ASSERTED**.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.40 — Endogenous Predictive Signaling

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** - C1–C5: **ASSERTED** across 5/5 seeds. - C6–C18: **NOT ASSERTED**. - C19: **ASSERTED** across 5/5 seeds. - C20–C24: **NOT ASSERTED**. - C25: **ASSERTED** across 5/5 seeds. The generic bounded I substrate physically perturbed the existing 4.39 N, and selective I→N ablation removed the injected effect. Ordinary experience acquired two distinct precursor→future-body→future-N structures, and contradictory experience revised those predictions. Learned prediction produced no current I. Consequently, there was no acquired pre-event N modulation, history-dependent present dynamics, future-specific internal correspondence, revision of I/N, or motor consequence. These NULLs were preserved rather than inferred away from successful infrastructure. First unsupported arrow: `acquired_prediction -X-> endogenous_signal_generation` Strongest supported claim: A bounded generic endogenous signal can physically participate in the intrinsic sensorimotor dynamics established in 4.39. This says nothing about learning or subjective anticipation. Historical NULLs from 4.37, 4.38, and 4.39 remain unchanged. `leak = []`.

**WHAT IT MEANS:** - C1–C5: **ASSERTED** across 5/5 seeds. - C6–C18: **NOT ASSERTED**. - C19: **ASSERTED** across 5/5 seeds. - C20–C24: **NOT ASSERTED**. - C25: **ASSERTED** across 5/5 seeds. The generic bounded I substrate physically perturbed the existing 4.39 N, and selective I→N ablation removed the injected effect. Ordinary experience acquired two distinct precursor→future-body→future-N structures, and contradictory experience revised those predictions. Learned prediction produced no current I. Consequently, there was no acquired pre-event N modulation, history-dependent present dynamics, future-specific internal correspondence, revision of I/N, or motor consequence. These NULLs were preserved rather than

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.41 — Acquired Internal Dynamics

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** All C1–C30 were **ASSERTED** across 5/5 canonical seeds. Ordinary temporal experience modified a bounded 3×3 internal coupling matrix using only local activity and a decaying eligibility trace. The same current numeric precursor subsequently produced history-specific internal activity at matched present physical state. The result survived: - temporally shuffled, iid, X-only, and Y-only controls; - plasticity-off and post-acquisition W ablations; - runtime explicit-prediction ablation; - future-event omission; - `ordinary_state_value` and legacy-logit neutralization; - compatible raw-history purge; - all five canonical seeds. Different X→Y and X→Z histories produced distinguishable X-triggered trajectories. Two acquired relations coexisted in the fixed substrate. Reversal revised W and downstream q/I/N; relation removal altered the effect, and restoration formed it again. Acquired internal activity propagated through the independently established 4.40 I→N interface and unchanged 4.39 N→motor dynamics. Selective I→N ablation preserved upstream q/I while removing the N contribution. No causal chain has an unsupported arrow in the tested claim ladder. Strongest supported statement: Ordinary temporal experience modified bounded internal coupling such that a later precursor generated acquired history-specific endogenous activity, which propagated through independently established end

**WHAT IT MEANS:** All C1–C30 were **ASSERTED** across 5/5 canonical seeds. Ordinary temporal experience modified a bounded 3×3 internal coupling matrix using only local activity and a decaying eligibility trace. The same current numeric precursor subsequently produced history-specific internal activity at matched present physical state. The result survived: - temporally shuffled, iid, X-only, and Y-only controls; - plasticity-off and post-acquisition W ablations; - runtime explicit-prediction ablation; - future-event omission; - `ordinary_state_value` and legacy-logit neutralization; - compatible raw-history purge; - all five canonical seeds. Different X→Y and X→Z histories produced distinguishable X-triggere

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.42 — Body-Coupled Development

**QUESTION:** Different developmental histories produced different autonomous physical intervention distributions under matched present conditions through acquired internal dynamics, independently of runtime explicit prediction and the legacy ordinary_state_value pathway. Not claimed: the distal body relation is what produced that intervention shift (C7 NOT ASSERTED). Not claimed: the shift alters later body trajectory (C22/C24 NOT ASSERTED). Not claimed: hunger, desire, goal, homeostasis, intention, planning.

**CHANGE:** No `.git` in `<local-lab-tree>`. Existing persist `EMIT` / `action_relief` unused. 4.42 adds only distinct X vs A_PAT channels, delayed distal body on `internal_a`/`load_c`, and the probe/control suite. 4.41 learning rule unchanged. M1 is physical A because A_PAT is channel 1.

**TEST / RESULT:** Autonomous intervention probability changes under matched present conditions. The expected future body trajectory does **not** diverge enough to assert regulation. 30 / 34 claims ASSERTED across seeds 17, 23, 41, 59, 83. `leak = []` This replaces an earlier untrustworthy pass that asserted Outcome F with C3 forced `or True` and identical X/A patterns.

**WHAT IT MEANS:** Autonomous intervention probability changes under matched present conditions. The expected future body trajectory does **not** diverge enough to assert regulation. 30 / 34 claims ASSERTED across seeds 17, 23, 41, 59, 83. `leak = []` This replaces an earlier untrustworthy pass that asserted Outcome F with C3 forced `or True` and identical X/A patterns.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Do **not** implement self-generated development. Follow the first unsupported FUTURE arrow (C22): the acquired ΔP(A) ≈ 0.021 does not move expected B past 0.004. Separately, C7 shows the motor shift is X→A coupling, not X→A→B. A later probe should ask whether a larger or more body-specific motor displacement can appear without installing a preference or policy.

## EXP-4.43 — Distal Consequence

**QUESTION:** A distal physical consequence contributed to acquired internal dynamics such that matched present conditions later produced different endogenous activity from otherwise matched proximal histories. Not Level 4/5. Not credit assignment, reward, intention, preference, regulation.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** A distal physical consequence contributes additional bounded W and later q/I/N under a matched present X. It does **not** produce a reproducible distal-specific P(A) shift. 4.42 C7 is resolved at acquisition/dynamics, not at motor. 27 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []` Learning rule unchanged (`TRACE_DECAY=0.62`, `LEARNING_RATE=0.075`). Invalid 4.42 Outcome F was not restored. 4.42 remains Outcome C. C22 threshold 0.004 was not moved.

**WHAT IT MEANS:** A distal physical consequence contributes additional bounded W and later q/I/N under a matched present X. It does **not** produce a reproducible distal-specific P(A) shift. 4.42 C7 is resolved at acquisition/dynamics, not at motor. 27 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []` Learning rule unchanged (`TRACE_DECAY=0.62`, `LEARNING_RATE=0.075`). Invalid 4.42 Outcome F was not restored. 4.42 remains Outcome C. C22 threshold 0.004 was not moved.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** C29/C30 NOT ASSERTED. Stay at the readout boundary: distal-specific q/I/N  -X->  autonomous P(A) Do **not** implement self-generated / recursive development. Do not extend eligibility or raise motor gain to cross 0.01 or 0.004.

## EXP-4.43-SELF-GENERATED-DEVELOPMENT — Self-Generated Development

**QUESTION:** - C1_endogenous_action_occurs: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C2_endogenous_A_physical_success: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C3_endogenous_experience_logged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C4_autonomous_W_change: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C5_plasticity_necessity: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C6_beyond_decay_baseline: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C7_motor_path_necessity: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C8_physical_A_necessity: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C9_bootstrap_alters_baseline: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C10_self_generated_further_W_change: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C11_recursive_probe_shift: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C12_plasticity_mediates_probe_shift: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C13_not_researcher_forced_in_auto: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C14_yoked_matched_actions: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C15_yoked_W_path_distinct_or_matched: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C16_force_vs_endogenous_distinguishable: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C17_naive_spontaneous_also_learns: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C18_bootstrap_plus_auto_exceeds_naive_auto: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C19_consequence_specificity: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C20_reversal_revises_W: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C21_prediction_independence: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C22_valuation_independence: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C23_raw_history_independence: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C24_boundedness: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C25_recursive_closed_loop: **ASSERTED** seeds=[17, 23, 41, 59

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Self-generated experience recursively modifies W and later dynamics without researcher-forced A, prediction, or OSV.

**WHAT IT MEANS:** Self-generated experience recursively modifies W and later dynamics without researcher-forced A, prediction, or OSV.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.44 — Body × Acquired Dynamics

**QUESTION:** 1. Same acquired history, different body, different motor? Body changes P(A) (main effect). History ΔP(A) stays ≈ −0.005 at MID and −0.004/−0.010 at HIGH/LOW. Not a body-gated distal-A effect. 2. Non-additive or sum of mains? Additive. Residual max |r| ≈ 0.0019 < 0.004. Span of Δ_history ≈ 0.0061 < 0.008. Tiny softmax curvature only. 3. At the same instantaneous body, does recent trajectory matter? No. T_DOWN vs T_UP end at B_MID; q L1=0; ΔP(A)≈0.001. 4. What would carry trajectory dependence? Only N persistence. After complete-state match (reset q/I/N), ΔP(A)=0. No extra historical variable. 5. Does distal history become motor-relevant anywhere in the tested body space without changing readout? **No.**

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Current body and acquired distal history each change endogenous dynamics. They do **not** interact in q, I, or N. Softmax produces a small motor residual below the preregistered interaction criterion. 20 / 31 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []` Motor readout was not changed. 4.43 0.01 bar was not reused as the interaction definition. SPAN_MIN=0.008, RESIDUAL_MIN=0.004, written before factorial outcomes.

**WHAT IT MEANS:** Current body and acquired distal history each change endogenous dynamics. They do **not** interact in q, I, or N. Softmax produces a small motor residual below the preregistered interaction criterion. 20 / 31 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []` Motor readout was not changed. 4.43 0.01 bar was not reused as the interaction definition. SPAN_MIN=0.008, RESIDUAL_MIN=0.004, written before factorial outcomes.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Stay at internal integration/readout. Body and W add in N; the distal difference remains motor-orthogonal. Do not raise motor gain, do not install a reason/value variable, do not start recursive development.

## EXP-4.45 — World–Body Co-development

**QUESTION:** Different developmental relations between external physical processes and the organism's own body-state trajectories produced persistent acquired internal structure. Under matched present world/body conditions, the same probe regenerated history-specific endogenous dynamics after removable raw history and transient state were controlled. Shorter: past world-body co-development altered present endogenous dynamics. Not claimed: autobiographical memory, self, identity, body ownership, subjective past, preference, motivation.

**CHANGE:** Body does not enter `step()` by itself. 4.45 only constructs `u` as `(world, 0, 0)` then `(0, body, 0)`. Learning rule unchanged. Ablating either channel removes the joint effect. No raw-history lookup.

**TEST / RESULT:** Different temporal pairings of the same world-state and body-state marginals produced different bounded W. Under PRESENT-2 (q/I/N reset, W kept) the same probe regenerated history-specific q, I, and N. Motor difference is **not** supported (ΔP(A) ≈ 0.0057 < 0.01). Readout was not changed. This matches the 4.44 motor-orthogonal boundary. 29 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []`

**WHAT IT MEANS:** Different temporal pairings of the same world-state and body-state marginals produced different bounded W. Under PRESENT-2 (q/I/N reset, W kept) the same probe regenerated history-specific q, I, and N. Motor difference is **not** supported (ΔP(A) ≈ 0.0057 < 0.01). Readout was not changed. This matches the 4.44 motor-orthogonal boundary. 29 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []`

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Smallest next ask: why joint-structure ΔN still fails to move P(A) — the same readout-orthogonality as 4.44. Do not add gain, reward, or self-model. Do not implement 4.46 in this update.

## EXP-4.46 — Acquired Sensorimotor Coupling

**QUESTION:** - C1_generic_N_channels: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C2_generic_M_channels: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C3_R_init_neutral: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C4_local_NM_only: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C5_matched_N_marginals: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C6_matched_M_marginals: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C7_temporal_relation_differs: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C8_R_modified: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C9_HA_HB_distinct_R: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C10_shuffled_not_full: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C11_N_only_not_full: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C12_M_only_not_full: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C13_same_N1_preactivation: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C14_same_N1_distribution: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C15_relation_specific: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C16_R_reset_removes: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C17_plasticity_off: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C18_eligibility_ablation: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C19_survives_prediction_ablation: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C20_survives_OSV: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C21_W_not_required: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C22_probe_geometry: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C23_unpaired_comparatively_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C24_reversal_revises: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C25_relation_removal_updates: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C26_R_bounded: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C27_constant_storage: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C28_endogenous_N_uses_R: **NOT ASSERTED*

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Matched-marginal pairing produces different bounded R and history-specific motor on the same N probe; endogenous N not cleanly demonstrated. 33 / 34 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT MEANS:** Matched-marginal pairing produces different bounded R and history-specific motor on the same N probe; endogenous N not cleanly demonstrated. 33 / 34 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Can an endogenous N that already differs by 4.41/4.45 history use this acquired R, without retuning gain? Do not implement 4.47 here.

## EXP-4.47 — Endogenous Motor Access Diagnostic

**QUESTION:** - C1_446_reproduces_D: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C2_probe_reproduces: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C3_endo_below_historical: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C4_endo_N_captured: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C5_probe_N_captured: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C6_magnitude_differs: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C7_direction_differs: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C8_dR_subspace: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C9_probe_projects: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C10_endo_projects: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C11_projection_predicts: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C12_amplitude_match_reproduces_probe: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C13_direction_match_reproduces_probe: **NOT ASSERTED** seeds=[] - C14_sweep_smooth: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C15_endo_replay_matches_ordinary: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C16_endo_replay_differs: **NOT ASSERTED** seeds=[] - C17_probe_at_endo_boundary: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C18_matched_vector_deterministic: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C19_pathway_diff_attributed: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C20_temporal_vs_snapshot: **NOT ASSERTED** seeds=[] - C21_shuffle_changes: **NOT ASSERTED** seeds=[] - C22_operating_point: **NOT ASSERTED** seeds=[] - C23_fixed_readout_nonlinear: **NOT ASSERTED** seeds=[17, 23, 41, 83] - C24_stochastic_explains: **NOT ASSERTED** seeds=[] - C25_prestochastic_endo_present: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C26_endo_weak_subspace: **NOT ASSERTED** seeds=[] - C27_no_gain_change: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C28_no_R_change: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C29_no_qIN_change: **ASSERTED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Difference is primarily explained by amplitude. 27 / 35 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT MEANS:** Difference is primarily explained by amplitude. 27 / 35 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If ordinary evolve() N is this small, does any *existing* endogenous source (I, or 4.41 q without 4.45 biography) produce N that occupies the acquired ΔR subspace at probe-like magnitude — without raising gain? Do not implement 4.48 here.

## EXP-4.48 — Endogenous Dynamic Range

**QUESTION:** - C1_446_D: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C2_447_B: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C3_N_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C4_R_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C5_no_gain_change: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C6_no_feedback: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C7_nat_amp_dist: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C8_nat_occupancy: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C9_nat_subspace: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C10_effective_drive: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C11_447_predicts: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C12_obs_follows_pred: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C13_q_contributes: **NOT ASSERTED** seeds=[] - C14_I_contributes: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C15_body_contributes: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C16_sources_cooccur: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C17_nat_amp_above_447: **NOT ASSERTED** seeds=[] - C18_nat_drive_above_447: **NOT ASSERTED** seeds=[] - C19_nat_reaches_0.02: **NOT ASSERTED** seeds=[] - C20_threshold_all_seeds: **NOT ASSERTED** seeds=[] - C21_not_probe: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C22_not_instrumentation: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C23_not_changed_R: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C24_not_changed_readout: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C25_not_changed_gain: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C26_geometry_compatible: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C27_attenuation_is_amp: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C28_duration_measured: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C29_not_single_seed: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C30_bounded_storage: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C31_no_rewar

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Existing natural runtime occupies only a low-amplitude N regime and does not substantially exceed the canonical 4.47 endogenous state. 30 / 35 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT MEANS:** Existing natural runtime occupies only a low-amplitude N regime and does not substantially exceed the canonical 4.47 endogenous state. 30 / 35 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Given this natural range, is there a *future* integration (not 4.48) in which 4.41 q from ordinary (non-biography) experience occupies the strong-R regime often enough to matter — still without raising gain? Do not implement 4.49 here.

## EXP-4.49 — Ordinary Physical Excitation

**QUESTION:** - C1_448_A: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C2_qIN_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C3_R_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C4_no_gain: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C5_candidate_exists: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C6_no_semantic_label: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C7_local_physical: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C8_accessible_sample: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C9_reaches_u: **NOT ASSERTED** seeds=[] - C10_u_from_physics: **NOT ASSERTED** seeds=[] - C11_u_changes_q: **NOT ASSERTED** seeds=[] - C12_qI_respond: **NOT ASSERTED** seeds=[] - C13_N_via_unchanged: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C14_N_above_448_median: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C15_N_above_448_p95: **NOT ASSERTED** seeds=[] - C16_N_above_448_max: **NOT ASSERTED** seeds=[] - C17_dR_projection: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C18_drive_above_448: **NOT ASSERTED** seeds=[] - C19_447_predicts: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C20_obs_matches_pred: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C21_RA_vs_RB_history: **NOT ASSERTED** seeds=[] - C22_not_fixed_alone: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C23_R_reset_removes: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C24_absent_reduces_u: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C25_decouple_reduces_field: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C26_u_ablation: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C27_no_qIN_injection: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C28_no_reward: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C29_no_source_id: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C30_reproduces: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C31_intensity_scales_field: **ASSERTED** seeds=[17, 23, 41, 59, 83] - C32_s

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** The existing architecture lacked a physically grounded ordinary pathway from world/body processes into the internal excitation input used by the acquired-dynamics mechanism. 27 / 38 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT MEANS:** The existing architecture lacked a physically grounded ordinary pathway from world/body processes into the internal excitation input used by the acquired-dynamics mechanism. 27 / 38 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = []

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Should a later update add the smallest physically grounded world→u bridge, or is body→N (4.39) the only ordinary physical entry that should exist? Do not implement 4.50 here.

## EXP-4.50 — World → Body → Motor Access

**QUESTION:** - C37 spontaneous world→body event class (default process config off) - C38 spontaneous body→N from that event - C39 spontaneous acquired-R motor effect

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** An ordinary physical world–body interaction altered existing body state, which propagated through unchanged intrinsic sensorimotor dynamics and previously acquired sensorimotor coupling into a history-specific motor distribution. 39 / 42 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] Spontaneous default runtime does not enter the same regime (C37/C38/C39 NOT ASSERTED). 4.51 not implemented. No world→u. No gain change. 4.45 unused.

**WHAT IT MEANS:** An ordinary physical world–body interaction altered existing body state, which propagated through unchanged intrinsic sensorimotor dynamics and previously acquired sensorimotor coupling into a history-specific motor distribution. 39 / 42 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] Spontaneous default runtime does not enter the same regime (C37/C38/C39 NOT ASSERTED). 4.51 not implemented. No world→u. No gain change. 4.45 unused.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Does any already-enabled ordinary runtime path write a 4.39 body variable, or is the default-off 4.20 process gate the entire remaining break between staged Outcome D and spontaneous runtime? Do not add a world→u bridge. Do not implement 4.51. Do not raise gain.

## EXP-4.51 — update451 activity physiology v0451

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **B + C** demonstrated. Not D/E. Cognitive **F/G** not claimed yet.

**WHAT IT MEANS:** **B + C** demonstrated. Not D/E. Cognitive **F/G** not claimed yet.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.51-DEFAULT-RUNTIME-BODY-ACCESS — Default Runtime Body Access

**QUESTION:** The architecture contains a physically valid world→body→N route demonstrated in 4.50, but no default-enabled world-dependent process was found to write the body variables used by 4.39. The remaining break is configuration/ecology rather than the intrinsic sensorimotor pathway. Not claimed: desire, motivation, reward, agency, salience.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** The architecture contains a physically valid world→body→N route demonstrated in 4.50, but no default-enabled world-dependent process was found to write the body variables used by 4.39. The remaining break is configuration/ecology rather than the intrinsic sensorimotor pathway. 26 / 42 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] 4.52 not implemented. Defaults unchanged. No world→u / world→body / world→N. 4.45 unused.

**WHAT IT MEANS:** The architecture contains a physically valid world→body→N route demonstrated in 4.50, but no default-enabled world-dependent process was found to write the body variables used by 4.39. The remaining break is configuration/ecology rather than the intrinsic sensorimotor pathway. 26 / 42 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] 4.52 not implemented. Defaults unchanged. No world→u / world→body / world→N. 4.45 unused.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If the only remaining WORLD→4.39-body break is the default-off 4.20 gate, is enabling that existing config ever part of ordinary ecology, or is a closed door the intended default runtime?

## EXP-4.52 — Early Physical Ecology

**QUESTION:** Ecology contrasts were not separable from seed/stochastic divergence or exposure-magnitude differences. Not: personality, upbringing, childhood, desire, reward, preference.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Ecology contrasts were not separable from seed/stochastic divergence or exposure-magnitude differences. 31 / 46 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] Default `persistent_process_config` remains None. 4.53 not implemented. No world→u. No new pathway.

**WHAT IT MEANS:** Ecology contrasts were not separable from seed/stochastic divergence or exposure-magnitude differences. 31 / 46 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] Default `persistent_process_config` remains None. 4.53 not implemented. No world→u. No new pathway.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If seed-level motor sampling swamps ecology-specific R, can a later study hold sampled M matched across cohorts (without adding a new rule) so temporal body history is the only free variable? Do not implement 4.53 here. Do not turn 4.20 on by default.

## EXP-4.53 — Matched Motor History × Body History

**QUESTION:** With body marginals and motor history controlled, changing the temporal relation between body-derived internal activity and motor samples changed the acquired sensorimotor coupling, supporting local temporal sensorimotor-history dependence. Not: upbringing, personality, desire, preference, reward learning, reinforcement, motivation, intention, goal-directed behavior.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** With body marginals and motor history controlled, changing the temporal relation between body-derived internal activity and motor samples changed the acquired sensorimotor coupling, supporting local temporal sensorimotor-history dependence. 39 / 48 claims ASSERTED. Streams [17, 23, 41, 59, 83]. leak = [] Default `persistent_process_config` remains None. 4.54 not implemented. No world→u. No new pathway. No R/W/motor rule change.

**WHAT IT MEANS:** With body marginals and motor history controlled, changing the temporal relation between body-derived internal activity and motor samples changed the acquired sensorimotor coupling, supporting local temporal sensorimotor-history dependence. 39 / 48 claims ASSERTED. Streams [17, 23, 41, 59, 83]. leak = [] Default `persistent_process_config` remains None. 4.54 not implemented. No world→u. No new pathway. No R/W/motor rule change.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If paired body-history → R is real under matched M, does any already-enabled ordinary runtime path ever produce the selected non-saturating pulse ecology — or is that schedule still a researcher gate? Do not implement 4.54 here. Do not turn 4.20 on by default. Do not change R or motor sampling.

## EXP-4.54 — Ordinary Physical Ecology Diagnostic

**QUESTION:** No already-enabled ordinary world-dependent process was found to write the body variables currently consumed by intrinsic sensorimotor dynamics. The temporal physical ecology used in 4.53 therefore remains researcher-enabled rather than ordinary runtime behavior. Not: curiosity, preference, upbringing, personality, desire, reinforcement.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** No already-enabled ordinary world-dependent process was found to write the body variables currently consumed by intrinsic sensorimotor dynamics. The temporal physical ecology used in 4.53 therefore remains researcher-enabled rather than ordinary runtime behavior. 23 / 48 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] 4.55 not implemented. Defaults unchanged. 4.20 not enabled. PULSE8 not used as ordinary evidence. Section 24 NOT_RUN.

**WHAT IT MEANS:** No already-enabled ordinary world-dependent process was found to write the body variables currently consumed by intrinsic sensorimotor dynamics. The temporal physical ecology used in 4.53 therefore remains researcher-enabled rather than ordinary runtime behavior. 23 / 48 claims ASSERTED. Seeds [17, 23, 41, 59, 83]. leak = [] 4.55 not implemented. Defaults unchanged. 4.20 not enabled. PULSE8 not used as ordinary evidence. Section 24 NOT_RUN.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If ordinary runtime still has no writer to the 4.39 keys, is that closed door the intended long-term default — or is enabling the existing 4.20 config ever part of ordinary ecology? Do not implement 4.55 here. Do not turn 4.20 on.

## EXP-4.55 — Existing Physiology Compatibility

**QUESTION:** Recorded ordinary physiological trajectories, without reward or semantic body labels, produced functionally distinct acquired sensorimotor couplings under controlled replay through existing intrinsic-dynamics and sensorimotor-plasticity mechanisms. No ordinary physiology→intrinsic-dynamics runtime connection was added. Not: preference, reward, homeostasis, comfort, integration.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Recorded ordinary physiological trajectories, without reward or semantic body labels, produced functionally distinct acquired sensorimotor couplings under controlled replay through existing intrinsic-dynamics and sensorimotor-plasticity mechanisms. No ordinary physiology→intrinsic-dynamics runtime connection was added. 48 / 48 claims. leak = [] Ordinary physiology→4.39 wiring remains **absent**. 4.56 not implemented. 4.20 not enabled.

**WHAT IT MEANS:** Recorded ordinary physiological trajectories, without reward or semantic body labels, produced functionally distinct acquired sensorimotor couplings under controlled replay through existing intrinsic-dynamics and sensorimotor-plasticity mechanisms. No ordinary physiology→intrinsic-dynamics runtime connection was added. 48 / 48 claims. leak = [] Ordinary physiology→4.39 wiring remains **absent**. 4.56 not implemented. 4.20 not enabled.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** If ordinary physiology is compatible with 4.39/R under researcher replay, what if anything physically justifies making one of these numeric relationships part of the organism rather than part of the researcher? Do not implement 4.56. Do not wire physiology into 4.39.

## EXP-4.56 — update456 generic physical transduction

**QUESTION:** C43 controlled probe, C44 R-reset mediation of motor, C58 autonomous later motor, C59 R-plasticity ablation of later motor, C62 full closed loop. Regressions 4.39–4.56: 79 passed, 0 failed. Semantic leak []. No reward/value/homeostasis/desire. No 4.57. No default bridge.

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** H_ABSOLUTE: Phase A pass WAIT+FREE; Phase B pass WAIT+FREE; live B→X→N both modes. H_CHANGE: Phase A fail WAIT (vs const L1 0.0199 < 0.02), pass FREE; Phase B fail both (FREE N L2 max 0.047, at noise). Both hypotheses reported. Neither declared "better" by ΔR. WAIT FAT-style ΔR is not a privileged mapping: assignment is structural order + MIX. Constant-body X: late Δ 2e-5 (ABSOLUTE) / 0 (CHANGE). Changing-body X: L2 max 0.722 (WAIT ABSOLUTE), clip 0. N above noise under ABSOLUTE (L2 max ~0.26 vs floor 0.039). N clip 0. Transducer OFF vs_off L1 0.312. Body-input OFF vs_frozen N L1 0.485. Body-matched X=0, N=0.

**WHAT IT MEANS:** H_ABSOLUTE: Phase A pass WAIT+FREE; Phase B pass WAIT+FREE; live B→X→N both modes. H_CHANGE: Phase A fail WAIT (vs const L1 0.0199 < 0.02), pass FREE; Phase B fail both (FREE N L2 max 0.047, at noise). Both hypotheses reported. Neither declared "better" by ΔR. WAIT FAT-style ΔR is not a privileged mapping: assignment is structural order + MIX. Constant-body X: late Δ 2e-5 (ABSOLUTE) / 0 (CHANGE). Changing-body X: L2 max 0.722 (WAIT ABSOLUTE), clip 0. N above noise under ABSOLUTE (L2 max ~0.26 vs floor 0.039). N clip 0. Transducer OFF vs_off L1 0.312. Body-input OFF vs_frozen N L1 0.485. Body-matched X=0, N=0.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** Under this experimental bridge, what (if anything) would make acquired R functionally visible in motor distribution without changing 4.39/4.46 or enabling the transducer by default — still without reward, valence, or named physiology maps. Do not implement 4.57 in this update.

## EXP-4.57 — update457 motor pathway archaeology

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** - Controlled probe L1 = INTERNAL_MOTOR P(M) - Autonomous acquisition L1 0.228 = R weights - Autonomous later motor 1/5 = INTERNAL_MOTOR probe - Matched M* and WAIT `engine.step({WAIT})` = RESEARCHER_FORCED_ACTION

**WHAT IT MEANS:** - Controlled probe L1 = INTERNAL_MOTOR P(M) - Autonomous acquisition L1 0.228 = R weights - Autonomous later motor 1/5 = INTERNAL_MOTOR probe - Matched M* and WAIT `engine.step({WAIT})` = RESEARCHER_FORCED_ACTION

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.58 — update458 action space compatibility

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome B. 69 / 70 claims.** The internal motor system exposes a generic numeric representation, but the current physical action runtime does not expose a corresponding low-level generic effector interface. INTERNAL_REPRESENTATION_AVAILABLE: SUPPORTED (preact). PHYSICAL_EFFECTOR_SPACE_AVAILABLE: ABSENT. GENERIC_STRUCTURAL_COMPATIBILITY: NOT_SUPPORTED. PHYSICALLY_PRIVILEGED_MAPPING: ABSENT. PHYSICAL_COUPLING: NOT_TESTED. 4.59 not implemented. No mapping. No actuator.

**WHAT IT MEANS:** **Outcome B. 69 / 70 claims.** The internal motor system exposes a generic numeric representation, but the current physical action runtime does not expose a corresponding low-level generic effector interface. INTERNAL_REPRESENTATION_AVAILABLE: SUPPORTED (preact). PHYSICAL_EFFECTOR_SPACE_AVAILABLE: ABSENT. GENERIC_STRUCTURAL_COMPATIBILITY: NOT_SUPPORTED. PHYSICALLY_PRIVILEGED_MAPPING: ABSENT. PHYSICAL_COUPLING: NOT_TESTED. 4.59 not implemented. No mapping. No actuator.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.59 — update459 generic physical effector

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome F. 75 / 75 claims.** A bounded generic physical effector substrate produced repeatable local organism displacement through symmetric lattice geometry and remained constrained by the physical world under extended researcher stimulation. Scope: LOCOMOTION_ONLY. FIRST_UNSUPPORTED: NONE. PREACT_TO_EFFECTOR: ABSENT. 4.60 not implemented.

**WHAT IT MEANS:** **Outcome F. 75 / 75 claims.** A bounded generic physical effector substrate produced repeatable local organism displacement through symmetric lattice geometry and remained constrained by the physical world under extended researcher stimulation. Scope: LOCOMOTION_ONLY. FIRST_UNSUPPORTED: NONE. PREACT_TO_EFFECTOR: ABSENT. 4.60 not implemented.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.60 — update460 arbitrary physical coupling

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome F. 82 / 82.** Multiple preregistered arbitrary fixed couplings translated the same generic internal numeric representation into distinct reproducible physical effector trajectories and world-constrained movement without assigning semantic meaning to internal channels or optimizing the coupling. FIRST_UNSUPPORTED=NONE. Next gap=CONSEQUENCE_TO_ACQUIRED_CHANGE. 4.61 not implemented.

**WHAT IT MEANS:** **Outcome F. 82 / 82.** Multiple preregistered arbitrary fixed couplings translated the same generic internal numeric representation into distinct reproducible physical effector trajectories and world-constrained movement without assigning semantic meaning to internal channels or optimizing the coupling. FIRST_UNSUPPORTED=NONE. Next gap=CONSEQUENCE_TO_ACQUIRED_CHANGE. 4.61 not implemented.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.61 — update461 live operating range

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome B. 79 / 79.** Existing physical body transduction substantially expanded live internal and effector activity, but the resulting operating range remained below the unchanged physical transition threshold. first_by_regime={'R0': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R1': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R3': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R2': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD'} 4.62 not implemented.

**WHAT IT MEANS:** **Outcome B. 79 / 79.** Existing physical body transduction substantially expanded live internal and effector activity, but the resulting operating range remained below the unchanged physical transition threshold. first_by_regime={'R0': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R1': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R3': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD', 'R2': 'LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD'} 4.62 not implemented.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.62 — update462 amplitude budget

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome F. 84 / 84.** No single bottleneck explained the subthreshold regime; multiple existing bounded transformations jointly compressed or redirected the body-derived internal activity before lattice resolution. 4.61 Outcome B reproduced (R0 max Q 0.0659, R1 0.4629, R3 0.4622, threshold 0.60, 0 hops). EXISTING_RELEVANT_UNCOMPOSED = ABSENT. STRUCTURAL_FIRST_UNSUPPORTED = NONE through Q. OPERATING_RANGE_FIRST_UNSUPPORTED = LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD. 4.63 not implemented. No gain / threshold / C / D / E / Q / transducer change.

**WHAT IT MEANS:** **Outcome F. 84 / 84.** No single bottleneck explained the subthreshold regime; multiple existing bounded transformations jointly compressed or redirected the body-derived internal activity before lattice resolution. 4.61 Outcome B reproduced (R0 max Q 0.0659, R1 0.4629, R3 0.4622, threshold 0.60, 0 hops). EXISTING_RELEVANT_UNCOMPOSED = ABSENT. STRUCTURAL_FIRST_UNSUPPORTED = NONE through Q. OPERATING_RANGE_FIRST_UNSUPPORTED = LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD. 4.63 not implemented. No gain / threshold / C / D / E / Q / transducer change.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.63 — update463 existing physical ecology

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome A. 83 / 83.** Existing physical ecology did not materially alter body state relative to the basal empty-world control under WAIT. Interpretation: EXISTING_PASSIVE_ECOLOGY_BODY_RANGE_EXPANSION_NOT_SUPPORTED. ECO1/ECO2 (canonical objects, WAIT, no USE): NO_BODY_EFFECT. ECO3 (field geometry (0,0)): NO_BODY_EFFECT. Field ablation: NO_BODY_EFFECT (canonical field coupling is below the 0.01 BODY material threshold). Q max 0.46291 equals 4.62 R1. Threshold ticks 0. Hops 0. 4.64 not implemented.

**WHAT IT MEANS:** **Outcome A. 83 / 83.** Existing physical ecology did not materially alter body state relative to the basal empty-world control under WAIT. Interpretation: EXISTING_PASSIVE_ECOLOGY_BODY_RANGE_EXPANSION_NOT_SUPPORTED. ECO1/ECO2 (canonical objects, WAIT, no USE): NO_BODY_EFFECT. ECO3 (field geometry (0,0)): NO_BODY_EFFECT. Field ablation: NO_BODY_EFFECT (canonical field coupling is below the 0.01 BODY material threshold). Q max 0.46291 equals 4.62 R1. Threshold ticks 0. Hops 0. 4.64 not implemented.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.64 — update464 world body path audit

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** **Outcome E. 86 / 86.** Passive WORLD to relevant-BODY initiation is absent or numerically negligible in the existing ordinary/canonical range, while a generic-displacement return route to relevant BODY already exists in source (movement_cost on actual distance; position-dependent field sample). Strong WORLD to BODY effects require semantic Action.kind. Qualifiers: PASSIVE_WORLD_BODY_STRUCTURE_PRESENT, MATERIAL_PASSIVE_WORLD_BODY_ACCESS_NOT_SUPPORTED, MATERIAL_WORLD_BODY_ACCESS_SEMANTIC_ACTION_DEPENDENT, INITIATION_PATH_INCOMPLETE, RETURN_PATH_STRUCTURALLY_PRESENT, SEMANTIC_ACTION_BOOTSTRAP_DEPENDENCY, WORLD_BODY_PHYSICAL_INTERFACE_INCOMPLETE 4.65 was not implemented. No reward/value/homeostasis/desire. No consequence learning. No semantic motor mapping. Defaults unchanged.

**WHAT IT MEANS:** **Outcome E. 86 / 86.** Passive WORLD to relevant-BODY initiation is absent or numerically negligible in the existing ordinary/canonical range, while a generic-displacement return route to relevant BODY already exists in source (movement_cost on actual distance; position-dependent field sample). Strong WORLD to BODY effects require semantic Action.kind. Qualifiers: PASSIVE_WORLD_BODY_STRUCTURE_PRESENT, MATERIAL_PASSIVE_WORLD_BODY_ACCESS_NOT_SUPPORTED, MATERIAL_WORLD_BODY_ACCESS_SEMANTIC_ACTION_DEPENDENT, INITIATION_PATH_INCOMPLETE, RETURN_PATH_STRUCTURALLY_PRESENT, SEMANTIC_ACTION_BOOTSTRAP_DEPENDENCY, WORLD_BODY_PHYSICAL_INTERFACE_INCOMPLETE 4.65 was not implemented. No reward/value/homeost

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.65 — update465 minimal passive physical exchange

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** PASSIVE_WORLD_BODY_CAUSATION_SUPPORTED_WITH_CONFOUND Claims 87 / 87. Canonical: 4.56 E, 4.57 B, 4.58 B, 4.59 F, 4.60 F, 4.61 B, 4.62 F, 4.63 A, 4.64 E. One new capability: default-off `passive_physical_exchange_config` completing existing env-exchange → process_materials. Equation: acc = min(a * 1.0 * 0.008, 0.008, rem); process existing yields; material_a → energy_delta 0.8. WAIT only. No USE/MOVE/TAKE/PUSH/RELEASE/EMIT. Q not inspected. 4.66 not implemented. Materiality: BOUND_DOMINATED. max component difference 0.11524566545192114. mean 0.014510893335018725. last L1 0.0. World-cause ablation causal: True. Exchange ablation causal: True. Identity: True. Ordinary env_material_field remains empty. Ordinary default runtime unchanged. First unsupported arrow: frozen 4.65 WORLD/BODY initiation -X?-> sufficient live downstream operating range Strongest allowed claim: under a researcher-constructed local env_material_field and experimental config, WAIT-only local material exchange can change energy_reserve through existing 4.8/4.9 equations. Strongest prohibited interpretation: the organism wants energy, seeks resources, is rewarded, or has begun to move because of 4.65. No consequence learning. No reward/value/homeostasis/desire. No semantic motor mapping.

**WHAT IT MEANS:** PASSIVE_WORLD_BODY_CAUSATION_SUPPORTED_WITH_CONFOUND Claims 87 / 87. Canonical: 4.56 E, 4.57 B, 4.58 B, 4.59 F, 4.60 F, 4.61 B, 4.62 F, 4.63 A, 4.64 E. One new capability: default-off `passive_physical_exchange_config` completing existing env-exchange → process_materials. Equation: acc = min(a * 1.0 * 0.008, 0.008, rem); process existing yields; material_a → energy_delta 0.8. WAIT only. No USE/MOVE/TAKE/PUSH/RELEASE/EMIT. Q not inspected. 4.66 not implemented. Materiality: BOUND_DOMINATED. max component difference 0.11524566545192114. mean 0.014510893335018725. last L1 0.0. World-cause ablation causal: True. Exchange ablation causal: True. Identity: True. Ordinary env_material_field remains 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.66 — update466 frozen physical composition

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** LIVE_DOWNSTREAM_PROPAGATION_SUPPORTED PHYSICAL_OPERATING_RANGE_NOT_REACHED Claims 89 / 90. Canonical: 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. Frozen 4.65 WORLD/BODY composed through existing X/N/C/E/Q. WAIT. No hop forced. Threshold 0.60 unchanged. 4.67 not implemented. R1 global max Q 0.4629087937678672 (previous live max 0.46291). Classification {'C0': 'NO_OVERLAP', 'C1': 'NO_OVERLAP', 'C2': 'NO_OVERLAP', 'C3': 'NO_OVERLAP', 'C4': 'NO_OVERLAP'}. realized hops 0. First unsupported: frozen composed WORLD/BODY/internal chain -X-> 0.60 physical threshold

**WHAT IT MEANS:** LIVE_DOWNSTREAM_PROPAGATION_SUPPORTED PHYSICAL_OPERATING_RANGE_NOT_REACHED Claims 89 / 90. Canonical: 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. Frozen 4.65 WORLD/BODY composed through existing X/N/C/E/Q. WAIT. No hop forced. Threshold 0.60 unchanged. 4.67 not implemented. R1 global max Q 0.4629087937678672 (previous live max 0.46291). Classification {'C0': 'NO_OVERLAP', 'C1': 'NO_OVERLAP', 'C2': 'NO_OVERLAP', 'C3': 'NO_OVERLAP', 'C4': 'NO_OVERLAP'}. realized hops 0. First unsupported: frozen composed WORLD/BODY/internal chain -X-> 0.60 physical threshold

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.67 — update467 physical dof access audit

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_PHYSICAL_ACCESS_ARCHITECTURE Claims 85 / 85. Canonical: 4.66 B (qualified C39 metric), 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. 4.68 not implemented. No unused path composed. No disconnected DOF connected. Physical groups: 17. BODY fields: 25. Unused existing paths: 3 (strongest: 4.20→N). 4.66 anomaly: C39 MEASUREMENT_LIMITED. Per-tick X contrast 0.08650029352962663; run-max |X| identical. Projection: B3→ports2 (MIX rank 2). Saturation at energy floor |X|→0.4167. Do not implement 4.68. Do not compose U1. Do not widen 4.56. Do not raise field coeffs.

**WHAT IT MEANS:** MIXED_PHYSICAL_ACCESS_ARCHITECTURE Claims 85 / 85. Canonical: 4.66 B (qualified C39 metric), 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. 4.68 not implemented. No unused path composed. No disconnected DOF connected. Physical groups: 17. BODY fields: 25. Unused existing paths: 3 (strongest: 4.20→N). 4.66 anomaly: C39 MEASUREMENT_LIMITED. Per-tick X contrast 0.08650029352962663; run-max |X| identical. Projection: B3→ports2 (MIX rank 2). Saturation at energy floor |X|→0.4167. Do not implement 4.68. Do not compose U1. Do not widen 4.56. Do not raise field coeffs.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.68 — update468 persistent process provenance

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_PERSISTENT_PROCESS_PROVENANCE Claims 85 / 85. Canonical: 4.67 F (U1/U3 qualified), 4.66 B, 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. 4.69 not implemented. Q not used. Movement not tested.

**WHAT IT MEANS:** MIXED_PERSISTENT_PROCESS_PROVENANCE Claims 85 / 85. Canonical: 4.67 F (U1/U3 qualified), 4.66 B, 4.65 E, 4.64 E, 4.63 A, 4.62 F, 4.61 B, 4.60 F, 4.59 F. Zero new capability. 4.69 not implemented. Q not used. Movement not tested.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.69 — update469 frozen physical composition

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** PHYSICAL_OUTPUT_WITH_RETURN_PATH Claims 93 / 93. Canonical: 4.68 F, 4.67 F, 4.66 B, 4.65 E. Zero new capability. 4.70 not implemented. Q not optimized. Movement was an outcome, not a target.

**WHAT IT MEANS:** PHYSICAL_OUTPUT_WITH_RETURN_PATH Claims 93 / 93. Canonical: 4.68 F, 4.67 F, 4.66 B, 4.65 E. Zero new capability. 4.70 not implemented. Q not optimized. Movement was an outcome, not a target.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.70 — update470 generic action body internal return

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** RETURN_PATH_SATURATION_LIMITED Claims 93 / 93. Canonical: 4.69 F, 4.68 F, 4.67 F, 4.66 B, 4.65 E. Zero new capability. 4.56 composed experimentally. 4.71 not implemented. Generator first letter was B (|X| linf delta 0). Reclassified to G after saturation analysis.

**WHAT IT MEANS:** RETURN_PATH_SATURATION_LIMITED Claims 93 / 93. Canonical: 4.69 F, 4.68 F, 4.67 F, 4.66 B, 4.65 E. Zero new capability. 4.56 composed experimentally. 4.71 not implemented. Generator first letter was B (|X| linf delta 0). Reclassified to G after saturation analysis.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.72 — update472 state dependent physical consequence

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_STATE_DEPENDENCE Claims 109 / 109. The same one-cell displacement, through existing `movement_cost` + clip01, has a realized BODY consequence that depends on pre-action BODY. Two existing mechanisms, both already in source: 1. effort = 1 + 0.8 F, so raw ΔE/ΔH/ΔF scale with fatigue. 2. clip01, so realized ΔF is 0 at F=1 and realized ΔE/ΔH are 0 at 0. Frozen prediction matches observation to 1e-9. 4.71 C1-like (0,0,1) DID is (0,0,0). C23-like (0,0,0.4) has ΔF=0.0132. That is the pilot explained, not a C effect. Live lattice confirm with a disclosed unit preact did not reach 0.60. Not chased. Primary is the transition(distance=1) path hops already call.

**WHAT IT MEANS:** MIXED_STATE_DEPENDENCE Claims 109 / 109. The same one-cell displacement, through existing `movement_cost` + clip01, has a realized BODY consequence that depends on pre-action BODY. Two existing mechanisms, both already in source: 1. effort = 1 + 0.8 F, so raw ΔE/ΔH/ΔF scale with fatigue. 2. clip01, so realized ΔF is 0 at F=1 and realized ΔE/ΔH are 0 at 0. Frozen prediction matches observation to 1e-9. 4.71 C1-like (0,0,1) DID is (0,0,0). C23-like (0,0,0.4) has ΔF=0.0132. That is the pilot explained, not a C effect. Live lattice confirm with a disclosed unit preact did not reach 0.60. Not chased. Primary is the transition(distance=1) path hops already call.

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.73 — update473 physical intervention vs nonintervention

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_PHYSICAL_TRAJECTORY_FATE Claims 121 / 121. From the same serialized BODY, EVENT (`distance=1`) and WAIT (`distance=0`) are research-only counterfactual branches through existing `BodyEngine.transition`. WAIT executes ordinary basal evolution (not a freeze). FROZEN_REFERENCE stays put. Interior (0.50,0.50,0.40): Δ0=(-0.015839999999999965, -0.005280000000000007, 0.01319999999999999) Δ12=(-0.015839999999999937, 0.0, 0.01319999999999999) fates={'energy': 'PERSISTENT_DIVERGENCE', 'hydration': 'TRANSIENT_DIVERGENCE', 'fatigue': 'PERSISTENT_DIVERGENCE'}. Bound F=1: Δ0=(-0.021599999999999953, -0.00720000000000004, 0.0) fates={'energy': 'PERSISTENT_DIVERGENCE', 'hydration': 'TRANSIENT_DIVERGENCE', 'fatigue': 'BOUND_ERASED'}. C1-like (0,0,1): Δ=(0.0, 0.0, 0.0) fates={'energy': 'BOUND_ERASED', 'hydration': 'BOUND_ERASED', 'fatigue': 'BOUND_ERASED'}. C23-like (0,0,0.40): Δ=(0.0, 0.0, 0.01319999999999999) fates={'energy': 'BOUND_ERASED', 'hydration': 'BOUND_ERASED', 'fatigue': 'PERSISTENT_DIVERGENCE'}. Frozen prediction matches to max err 1.1102230246251565e-16.

**WHAT IT MEANS:** MIXED_PHYSICAL_TRAJECTORY_FATE Claims 121 / 121. From the same serialized BODY, EVENT (`distance=1`) and WAIT (`distance=0`) are research-only counterfactual branches through existing `BodyEngine.transition`. WAIT executes ordinary basal evolution (not a freeze). FROZEN_REFERENCE stays put. Interior (0.50,0.50,0.40): Δ0=(-0.015839999999999965, -0.005280000000000007, 0.01319999999999999) Δ12=(-0.015839999999999937, 0.0, 0.01319999999999999) fates={'energy': 'PERSISTENT_DIVERGENCE', 'hydration': 'TRANSIENT_DIVERGENCE', 'fatigue': 'PERSISTENT_DIVERGENCE'}. Bound F=1: Δ0=(-0.021599999999999953, -0.00720000000000004, 0.0) fates={'energy': 'PERSISTENT_DIVERGENCE', 'hydration': 'TRANSIENT_DIVERGENC

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.74 — update474 body response consequence acquisition archaeology

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** MIXED_ACQUISITION_PATH Claims 118 / 118. The 4.72/4.73 movement-cost BODY consequence has no existing path into W or R. Ordinary BODY→N is absent (evolve ignores energy/hydration/fatigue). 4.56 can write X when enabled; maybe_step does not write live ports; X does not update W/R. W and R exist as other learners: - W associates successive researcher `u` - R associates earlier N with later internal M That is not response-consequence acquisition, and not contingency. Contingent/yoked: NOT_RUN (would require a new edge).

**WHAT IT MEANS:** MIXED_ACQUISITION_PATH Claims 118 / 118. The 4.72/4.73 movement-cost BODY consequence has no existing path into W or R. Ordinary BODY→N is absent (evolve ignores energy/hydration/fatigue). 4.56 can write X when enabled; maybe_step does not write live ports; X does not update W/R. W and R exist as other learners: - W associates successive researcher `u` - R associates earlier N with later internal M That is not response-consequence acquisition, and not contingency. Contingent/yoked: NOT_RUN (would require a new edge).

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.75 — update475 response contingent internal transition acquisition

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Outcome E: CONTINGENCY_SENSITIVE_ACQUISITION. 143/143. S=X_ABSOLUTE_SNAPSHOT. M=GENERIC_2VECTOR. L frobenius C1=0.003975328047744289 C2=0.004063962529396624 d12=0.004599862650311365. Allowed: A bounded neutral acquired structure was sensitive to experienced response-consequence pairing under matched marginal statistics. Prohibited: reward learning; reinforcement; preference; desire; motivation; goal; homeostatic regulation; learning what is good; learning what response to repeat; causal understanding; choice; decision; prospection; 4.76 Next: Can the acquired transition structure causally alter current internal dynamics when the same internal pre-state is encountered again? Do not implement 4.76. 4.76 not implemented.

**WHAT IT MEANS:** Outcome E: CONTINGENCY_SENSITIVE_ACQUISITION. 143/143. S=X_ABSOLUTE_SNAPSHOT. M=GENERIC_2VECTOR. L frobenius C1=0.003975328047744289 C2=0.004063962529396624 d12=0.004599862650311365. Allowed: A bounded neutral acquired structure was sensitive to experienced response-consequence pairing under matched marginal statistics. Prohibited: reward learning; reinforcement; preference; desire; motivation; goal; homeostatic regulation; learning what is good; learning what response to repeat; causal understanding; choice; decision; prospection; 4.76 Next: Can the acquired transition structure causally alter current internal dynamics when the same internal pre-state is encountered again? Do not implement 

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## EXP-4.76 — update476 acquired transition reinstatement

**QUESTION:** NOT_RECORDED

**CHANGE:** NOT_RECORDED

**TEST / RESULT:** Outcome D: CONTINGENCY_SENSITIVE_REINSTATEMENT. 138/138. R = S^T L. R_C F=7.74474671196012e-05 R_Y F=9.15626228573287e-05 linf=0.00011499656625778412. Analytical err=0.0. EXACT_BILINEAR_PROPAGATION. Allowed: A bounded current internal reinstatement depended jointly on the present internal state and a previously acquired response-contingent transition structure; exact-marginal contingent and yoked histories produced different reinstatement under the same current state. The difference is the bilinear contraction of the already-different L tensors. Prohibited: memory of what worked; reward expectation; preference; desire; motivation; intention; goal; planning; prospection; choice; decision; regulation; action selection; 4.77 Next: Can the current acquired reinstatement causally enter an already-existing action-relevant internal pathway without introducing valuation or direct response selection? Do not implement 4.77. 4.77 not implemented.

**WHAT IT MEANS:** Outcome D: CONTINGENCY_SENSITIVE_REINSTATEMENT. 138/138. R = S^T L. R_C F=7.74474671196012e-05 R_Y F=9.15626228573287e-05 linf=0.00011499656625778412. Analytical err=0.0. EXACT_BILINEAR_PROPAGATION. Allowed: A bounded current internal reinstatement depended jointly on the present internal state and a previously acquired response-contingent transition structure; exact-marginal contingent and yoked histories produced different reinstatement under the same current state. The difference is the bilinear contraction of the already-different L tensors. Prohibited: memory of what worked; reward expectation; preference; desire; motivation; intention; goal; planning; prospection; choice; decision; reg

**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.

**NEXT QUESTION:** UNKNOWN

## PHYS-4.76-E1A — generic contact-coupled material transfer

**QUESTION:** Can generic same-cell contact enable existing bounded intake without USE/TAKE?

**CHANGE:** Shared apply_bounded_object_intake; contact_material_transfer_config default None.

**TEST / RESULT:** Outcome E GENERIC_CONTACT_TO_BODY_CHAIN. 91/91. PHYS-4.76-E1A

**WHAT IT MEANS:** geometric contact can drive existing transfer→internal→processing→BODY without semantic USE.

**WHAT IT DOES NOT MEAN:** Not eating/food/reward/motivation/seeking. Do not implement 4.77.

**NEXT QUESTION:** Resume ECO-4.76-E1?


## ECO-4.76-E1 — distal cue × contact consequence (resume after PHYS-4.76-E1A)

**QUESTION:** Dual distal PASSIVE_WAVE + contact BODY from one generic source; autonomous encounter?

**CHANGE:** None new. Enabled existing PHYS contact config + PASSIVE_WAVE.

**TEST / RESULT:** Historical K preserved. Resume Outcome F AUTONOMOUS_BODY_CONSEQUENCE_ESTABLISHED. 120/120. ECO-4.76-E1 Seeking/cue-causation NOT_CLAIMED.

**WHAT IT MEANS:** Dual source properties compose; ordinary Action.kind dynamics encountered source under frozen runs.

**WHAT IT DOES NOT MEAN:** Not seeking, navigation, food, reward, learning, or 4.77.

**NEXT QUESTION:** 4.75 compatibility with natural episodes? Do not implement 4.77.

## ECO-4.76-E2 — natural episode acquisition interface compatibility archaeology

**QUESTION:** Are natural ECO episodes directly compatible with existing 4.75 S/M/S_after interfaces?

**CHANGE:** None.

**TEST / RESULT:** Outcome L MIXED_INTERFACE_FATE. 125/125. ECO-4.76-E2 No acquisition. First unsupported: S_before.

**WHAT IT MEANS:** Experience exists; learner interfaces do not directly receive it.

**WHAT IT DOES NOT MEAN:** Not learning, seeking, adapters, or 4.77.

**NEXT QUESTION:** Natural state as canonical S without research surrogate? Do not implement 4.77.

## ECO-4.76-E3 — natural state representation archaeology

**QUESTION:** Ordinary natural S for 4.75 without adapters/enabling X?

**CHANGE:** None.

**TEST / RESULT:** Outcome H ONLY_EXPERIMENTAL_X_SATISFIES_REQUIREMENTS. 130/130. ECO-4.76-E3 best=NONE.

**WHAT IT MEANS:** Only experimental X structurally fits; ordinary unified S absent.

**WHAT IT DOES NOT MEAN:** Not learning; not enable X; not Action.kind→M; not 4.77.

**NEXT QUESTION:** Smallest physically justified ordinary state representation mechanism?
- **PHYS-4.76-E3A** (2026-09-13): Outcome E X_REIMPLEMENTATION_RISK — no new capability; do not invent X2; ports/dim supporting stops.
- **PHYS-4.76-E3B** (2026-09-13): Outcome C GENERIC_CORE_RESEARCH_SPECIFIC_INTERFACE — X hybrid core+shells; do not enable.
- **PHYS-4.76-E3C** (2026-09-13): Outcome C MULTIPLE_PARTIAL_BODY_TO_INTRINSIC_PATHS — fragmented experimental cables; ordinary BODY→N absent.
- **PHYS-4.76-E3D** (2026-09-13): Outcome E HISTORICALLY_REUSED_BODY_KEYS — ia/lc are laboratory/historical sockets, not ordinary privileged N ports.
- **PHYS-4.76-E3E** (2026-09-13): Outcome C HETEROGENEOUS_PHYSICAL_COUPLING_FAMILIES — ordinary physics multi-family; no universal F.
