# ACANTHOSTEGA · P4B CANONICAL RESPONSE ENCODING OPTIMIZATION V1

## Identity
- Schema: `OBSERVER_CANONICAL_RESPONSE_ENCODING_V1`
- Capability: `canonical_response_encoding_optimization`
- Profile: `AUTHORITY_PRESERVING_JSON_RESPONSE_ENCODING_P4B_V1`
- Authority: `DERIVED_TRANSPORT_OPTIMIZATION_NO_SCIENTIFIC_EFFECT`

## Verdict
**B. P4B_PASS_SAME_TICK_RESPONSE_CACHE_ONLY**

## Design
1. Authoritative derived frame (`current_frame` / `live_frame`) unchanged.
2. Canonical HTTP JSON encoder matches Starlette `JSONResponse.render`.
3. Bounded same-tick complete encoded-response cache for `GET /api/state`.
4. Serve `Response(content=bytes, media_type=application/json)` — skip repeated `jsonable_encoder`.
5. Invalidate on Apply/restore beside P4 fragment cache clears.
6. No orjson, no compression, no fragment string concat, no scientific mutation.

## Measured (isolated bench)
| Metric | Value |
|--------|-------|
| MAP Starlette encode p50/p95 | 6.7454550007823855 / 7.231594994664192 ms |
| MAP FastAPI jsonable+encode p95 | 30.253706994699314 ms |
| MAP cache-hit p50/p95 | 0.009006995242089033 / 0.01297399285249412 ms |
| VOLUME warm encode pre→hit p95 | 6.473986024502665 → 0.011791998986154795 ms |
| SURFACE warm encode pre→hit p95 | 34.168189013144 → 0.03913399996235967 ms |

## Next safe seam
P6 Analyzer optimization or backend O4 profiling (encode no longer dominates paused HTTP polls).
