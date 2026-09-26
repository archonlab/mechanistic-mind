# Beta 3.1 PE forgotten history representation

Read-path forensic for Predictive Equivalence classes after ACTIVE→FORGOTTEN.
Failed 40k corpus `e02e833b` and prior RSS owner artifacts were not rewritten.

## Verdict

Forgotten classes **never re-enter** learn, retrieve, relevance refresh, ACTIVE indexes, continuation comparison, or PSC. They remain in `store["classes"]` as historical rows. Wide member maps (`fragment`, `mean_c`, `last_abs`) are **not** consulted by production cognition after forget. Snapshot/Observer/V3 do not dump those maps. Persistence currently walks the live dict tree, so a compact lossless encoding is required if history is kept.

`FORGOTTEN_CAN_REACTIVATE = NO`  
`FORGOTTEN_AFFECTS_FUTURE_COGNITION = NO`

## Data model (operational vs historical)

ACTIVE class: full mutable members (up to 12) with per-member float dicts, AABB rebuilt from member fragments, class `mean_c` from member continuation means.

FORGOTTEN class (pre-compaction): same object graph, only `status` flipped and indexes dropped.

Dominant live width under R3 / RICH / CORRELATED / OCCLUSION: repeated channel keys × 3 maps × members, plus dict/float object overhead.

## Post-forget reads

| Surface | Forgotten fields used |
| --- | --- |
| `learn` / `retrieve` / relevance retrieve | none (ACTIVE only) |
| `pe.snapshot` | id, action, support, n_members, aabb_keys, status, revised_at (first 16 classes) |
| `prl.snapshot` | id, status, support, relevance compact lists |
| TPS snapshot / memory_usage | forgotten count, `len(members)` |
| dump_persist / restore | entire remaining class dict |
| tests | optional unpack of member fragment as a retrieve *query*, not as a forgotten match |

No relevant field left UNKNOWN.

## Representation decision

Do not delete forgotten classes. At forget-time, replace member float dicts with shared `_pack_keys` plus `array('d')` values and a presence bitmask. Expand is lossless (exact floats). ACTIVE path unchanged.

See `docs/BETA31_PE_FORGOTTEN_COMPACTION.md` for production packing, RSS, and remaining 40k blocker.
