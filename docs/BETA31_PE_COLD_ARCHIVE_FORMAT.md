# Beta 3.1 PE forgotten cold archive — format

Version: **PECA v1** (`pe.forgotten.cold.v1`). Little-endian. Not pickle.

## When it is written

Only if `predictive_equivalence.set_cold_archive(True)`. Production default is **off** (Hybrid G forgotten dicts remain in `store["classes"]`).

At `ACTIVE → FORGOTTEN` the class is packed (Hybrid G), appended to `_pe_cold`, then **removed** from `classes`. Learn/retrieve never read the archive.

## In-memory schema (store[`_pe_cold`])

| Field | Meaning |
| --- | --- |
| `rep` / `version` | `pe.forgotten.cold.v1` / `1` |
| `chunk_records` | 256 (measured; 128–1024 append cost equivalent ~54 µs/record on synthetic 24-key classes) |
| `schemas` | interned key tuples (one per distinct pack schema) |
| `actions` | interned action strings (includes `\|L{lag}`) |
| `chunks[]` | structure-of-arrays records |

Per chunk columns: `class_num` (uint32 of `E{n}`), `action_ix`, `support`, `first_tick`, `revised_at` (−1 = None), `schema_ix`, `n_members`, `member_base`, `float_off`, `mask_off`, `aux_off`/`aux_len`.

Member SOA: `mem_support`, `mem_contra`, `mem_first`, `mem_last`, `mem_sig_off`/`len` into `sig_blob`.

Float payload (`float64` array `d`): per class, for each member `fragment`, `mean_c`, `last_abs` (schema-aligned), then class `mean_c`, then AABB `lo[]`/`hi[]`. Presence bitmasks (`uint8`) in the same order (AABB has one mask).

`aux_blob`: UTF-8 JSON with `provenance`, `relevance` (last ACTIVE refresh), `raw_ids`, rare `id_fallback` / `aabb_extra`. Exact JSON round-trip of those structures.

IDs `E{n}` are stored as `n`. Non-conforming ids go to `id_fallback`.

## Disk sidecar (optional)

File = `magic "PECA"` + `uint16 version` + `uint32 meta_len` + UTF-8 JSON metadata (schemas, actions, endian=`little`, dtypes) + length-prefixed `array.tobytes()` for each column + `sig_blob` + `aux_blob` + `uint32 crc32` of the preceding body.

Truncated or bit-flipped files **fail** `verify_chunk_binary`. No silent scientifically plausible history.

JSON snapshots still `tolist()` the arrays through existing `dump_persist`. Restore `clear_derived_caches` re-materializes arrays. Cold JSON is large (numeric lists); the binary sidecar is the dense on-disk form.

## Reconstruction

`iter_cold_records(store, reconstruct=True)` rebuilds a Hybrid G packed forgotten class. `expand_forgotten_class` yields the full dict maps. Bit-identical float64 (`struct <d`) is required.
