# Beta 3.1 PE forgotten cold archive forensic

Historical 40k corpus `e02e833b` was not modified. Beta 3 reference frozen. No git push.

## Question

Forgotten PE history is **unique** (nested payload duplication = 0). Can it leave the Python object heap as an immutable dense archive without changing cognition or deleting science?

## Contract and immutability

`FORGOTTEN_HISTORICAL_CONTRACT_COMPLETE = YES` — see `results/beta31_pe_cold_archive/historical_contract.json`.

No forgotten field is required for **future cognition**. `learn` / `retrieve` / `predictive_relevance.refresh` are ACTIVE-only.

`FORGOTTEN_RECORD_IMMUTABLE_AFTER_FORGET = YES`. Probe-wrapped forgotten dicts recorded **no writes** during subsequent learn, retrieve, and relevance refresh. Compaction mutates only during the forget transition, before archival.

## Byte cost (seed 575, t1000, TwoAgent, matched failed-run mechanisms)

All stores, both agents, Hybrid G:

| | |
| --- | --- |
| Forgotten classes in Python | 13432 |
| Python representation | 399.6 MB (~29750 B/class) |
| Logical float/mask payload | 172.7 MB (~12859 B/class) |
| `PYTHON_OVERHEAD_RATIO` | **2.314** |

Outer PE sample (E1): 68 keys, ~11.3 KB reachable vs 3.3 KB logical. Nested temporal class: 272 keys, ~31 KB vs 13.2 KB logical. Schema tuples dominate the Python shell; values are already `array('d')`.

Cold SOA (same run, opt-in): **~13277 B/class** allocated — essentially the logical payload plus chunk headers. `MINIMUM_LOSSLESS_BYTES_PER_CLASS ≈ 13.3 KB` without shrinking float64 or merging classes.

`PYTHON_OBJECTS_PER_1000_FORGOTTEN_CLASSES`: Hybrid G ~3.2×10⁵ object nodes; cold archive O(chunks) ~2×10². Object-count reduction **99.93%**.

## Architecture

Default remains Hybrid G (`_COLD_ARCHIVE = False`).

Experimental: at forget, append to chunked SOA (`chunk_records=256`), pop the class from `classes`. Reconstruction and metadata streaming live in `mechanistic_mind/research/pe_cold_archive.py`. Optional PECA v1 sidecar with CRC.

## Equivalence (seed 575, 250 ticks)

| Gate | Result |
| --- | --- |
| Shadow (2689 forgets) | **100.0%** |
| Cognition (actions, observations, body, PE counters) | **EXACT** |
| Lifecycle (ids, support, forget counts, lag action strings) | **EXACT** |
| Historical payload | **EXACT** |
| Old full / Hybrid G / cold JSON restore + 5–8 tick continue | **PASS / EXACT** |
| Analyzer metadata stream | **YES** (0 RSS delta at t80) |

## Memory (t0–t1000, child processes)

| | Hybrid G | Cold RAM |
| --- | --- | --- |
| RSS t0 | 45.2 MB | 45.2 MB |
| RSS t1000 | 502.0 MB | 512.7 MB |
| RSS MB / 1000 (t0–t1000) | **456.8** | **467.5** |
| RSS t250→t1000 | 205.5→502.0 (**395.4**/1000) | 207.8→512.7 (**406.5**/1000) |
| Forgotten reachable | 381 MB | 170 MB (archive) |
| ticks/s | 6.63 | 6.47 |

**RSS did not fall.** Python reachable forgotten history did (~55%). RSS remains linear in forgotten-class count because (1) unique float64 history is already ~13 KB/class and stays in RAM, and (2) pymalloc arenas from ACTIVE member-map churn are not returned — a tiny forget probe showed `malloc_trim` dropping 393→241 MB as a **diagnostic only**. Cold then **adds** contiguous `array('d')` buffers while arenas stay resident, so RSS can even rise slightly.

`ALLOCATOR_AMPLIFICATION_REDUCED = PARTIAL` (reachable yes, process RSS no).

5k / 10k were **not** run: RSS was not materially improved. 40k was not run.

Projections from the cold t0–t1000 RSS slope (same OOM family as Hybrid G): 20k ~9.4 GB, 40k ~18.7 GB, 100k ~46.8 GB. 100-agent RAM history ~23 GB / 1000 ticks if linear in agents (projection only).

Disk sidecar ~51 MB / 1000 ticks extrapolated from t80 files; **does not bound RSS** unless sealed chunks leave RAM (not default; mmap release not enabled).

## Null result (valid)

Lossless dense archival **can** eliminate O(forgotten) Python graphs and reconstruct Hybrid G exactly **without** changing PE/TPS/TPE/cognition. It **cannot**, by itself, make 40k safe: the unique nested lag window-delta float64s are the historical information, and RSS is dominated by allocator residency plus that payload.

Do not manufacture a PASS by discarding history.

## Verdict

`BETA31_PE_COLD_ARCHIVE = PARTIAL`

Public Beta 3.1 remains blocked on the 40k OOM-class nested PE history slope. Default production representation is still Hybrid G.
