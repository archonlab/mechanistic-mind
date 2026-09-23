# MULTI-AGENT PARALLELISM AUDIT

**Verdict:** `MULTI_AGENT_PARALLELISM_SAFE_WITH_BARRIER`

**Practical (current CPython):** `NOT_WORTHWHILE_ON_CURRENT_CPYTHON`

No production runtime change. No semantic change. No git push.

## Executive answer

Two Tiktaaliks in one shared world **already observe the same tick-T snapshot** before either thinks. Their cognition (given frozen observations + agent-local stores + per-agent RNG) is **order-commutative within the tick**. They can therefore **safely think simultaneously** if a **barrier** preserves serial physical commit (`process_order` apply → planet → finish → contact/PUSH/SIGNAL/OSC).

On **current CPython**, threads **slow down** cognition (~0.89×) and multiprocessing must ship **~2.1 MB** of cognition state per tick for 2 agents — erasing the theoretical ~1.38× Amdahl gain. Scientifically safe ≠ practically useful yet.

## Phase 1 — Causal order

Source: `TwoAgentRuntime._step_once` + `PhysicalSystemRuntime.begin_tick` / `finish_tick`.

```
WORLD / BODY STATE T
        |
        v
 observations()     ALL agents  (Vision, SNF, OSC receptors, body, fields)
        |           SHARED_READ + AGENT_LOCAL_READ
        |
        +-- begin_tick(A): think + body impulse --+
        +-- begin_tick(B): think + body impulse --+  serial process_order
        |           think: AGENT_LOCAL_READ/WRITE + RNG_DEPENDENT
        |           apply: AGENT_LOCAL_WRITE (ORDER_DEPENDENT scheduling only)
        v
 step_planet(WORLD)     SHARED_WRITE
        |
        +-- finish_tick(A) --+
        +-- finish_tick(B) --+  SHARED_READ + AGENT_LOCAL_WRITE
        v
 contact / PUSH / resources / SIGNAL / OSC     SHARED_WRITE + ORDER_DEPENDENT
        |
        v
 WORLD / BODY STATE T+1
```

Stage classifications: `results/multi_agent_parallelism_audit/causal_order.json`.

## Phase 2–3 — Independence & same-tick semantics

**Possibility B** for cognition inputs (not A).

| Check | Result |
|-------|--------|
| `observations()` before any `begin_tick` | Yes |
| Shared cognition object | No (`construction_audit`) |
| Shared body / internal | No |
| Shared world | Yes |
| Cognition AB vs BA order | **Identical** selected actions + store digests |
| RNG | `_rng_unit(agent_seed, tick)` — closed form, independent streams |

Hidden shared mutable state (not semantic inputs, but thread hazards):

- module `_SIG_CACHE` (compression + PSC) — pure digests; **not thread-safe**
- module `_SNF_CACHE` — observation phase only
- per-runtime `_cognitive_view_cache`

**Barrier required** because `begin_tick` fuses think + motor apply, and all post-think physics/interaction is shared/order-dependent.

## Phase 4 — Per-agent cost (filled store, 2 agents)

From `per_agent_profile.json` (warm 220, measure 60):

| Stage | Mean ms/tick | ≈ % of tick |
|-------|--------------|-------------|
| Cognition agent 0 | ~10.0 | ~27% |
| Cognition agent 1 | ~10.5 | ~28% |
| PSC (compose) sum | ~11.0 | (inside cognition) |
| Motor apply (both) | ~1.3 | ~4% |
| Observations | ~3.6 | ~10% |
| finish_tick both | ~9 | ~25% |
| planet + interaction tail | ~6 | ~16% |
| **Total** | **~37** | 100% |

- Independently parallelizable cognition ≈ **56%** of tick wall
- Theoretical max 2-core speedup (think parallel, apply+physics serial): **~1.38×**
- Optimistic (entire begin parallel): **~1.41×**

## Phase 5 — Scaling 1 → 2 → 4 (filled stores)

| Agents | t/s | ms/tick | Store frac |
|--------|-----|---------|------------|
| 1 | ~54 | ~19 | 128/128 |
| 2 | ~28 | ~36 | 128/128 each |
| 4 | ~17 | ~59 | 128/128 each |

Ratios vs 1-agent: **1.93×** (2), **3.16×** (4) → approximately **O(agent count)** with mild sublinearity from shared planet/interaction.

## Phase 6 — Parallelization options

| Option | 2-agent likely benefit | Notes |
|--------|------------------------|-------|
| A Threading | **Negative** (measured 0.89×) | GIL; `_SIG_CACHE` races |
| B/C Multiprocessing / ProcessPool | **Negative** for 2 | ~2.1 MB pickle/tick; process one-shot ~156 ms vs ~19 ms serial think |
| D Free-threaded Python | Conditional | Needs partitioned/locked caches |
| E Numba | Unchanged prior NOT_WORTH_IT | Does not remove barrier |
| F C/C++ cognition | Best path to real multicore | Release GIL around compose/soft_match |
| G Hybrid barrier | Matches current semantics | observe-all → parallel think → serial commit |

## Phase 7 — Determinism / EXACT_MATCH plan

Seeds 17, 23, 41, 59, 83 (+ exposure-heavy): snapshot after fill → N ticks serial vs parallel-think+serial-commit → fingerprint world, bodies, internals, cognition stores, events, RNG digests. Preserve `process_order` for apply/finish. See `determinism_plan.json`.

Prototype thread path: **100%** selected-action / last_selection match vs serial on frozen inputs. Process path: selected actions matched on one-shot (payload size dominates).

## Phase 8 — Prototype

Isolated only (`prototype_parallel.json`). Production `TwoAgentRuntime` **unchanged**.

| Mode | Mean ms (2-agent think) | vs serial |
|------|-------------------------|-----------|
| Serial | ~19.5 | 1.00× |
| Threads | ~21.4 | **0.89×** |
| Process (1 shot incl. pickle) | ~156 | **0.12×** |

## Explicit answers

1. **Independent within one tick?** Yes — given frozen observations.
2. **Same snapshot or sequential worlds?** **Same snapshot T**; then serial apply.
3. **Parallelizable fraction?** ~**56%** cognition.
4. **Shared mutable state?** World; module caches; pairwise physics after think.
5. **RNG/order?** Per-agent `_rng_unit`; `process_order` for commit.
6. **Theoretical 2-agent speedup?** ~**1.38×**.
7. **Measured prototype?** Threads **0.89×**; process payload ~**2.1 MB**.
8. **1→2→4 scaling?** ~O(n), mild sublinear (1.93× / 3.16×).
9. **Threads help?** **No** (GIL).
10. **Multiprocessing help (2)?** **No** (serialization).
11. **Native/Numba/C++?** Would make agent-level parallel *implementation* viable by releasing GIL; semantics still need barrier.
12. **10+ agents?** Cost ~linear in agents; many-core only helps with shared-memory/native think; physics/interaction remain serial bottlenecks.
13. **EXACT_MATCH preservable?** **Yes**, with barrier + no cache races affecting purity.
14. **Scientifically safe?** **Yes**, with barrier — not as a naïve “parallelize `_step_once`” rewrite.

## Recommended next (not done here)

Only if a speedup is required: **shared-memory or native PSC** under a think/commit barrier — not Python multiprocessing of full cognition dicts, and not GIL-bound threads.

---

**MULTI_AGENT_PARALLELISM_SAFE_WITH_BARRIER**
